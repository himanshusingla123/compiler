# app.py (Corrected version)
import os
import subprocess
import threading
import queue
import uuid
import tempfile
import time
import platform
import signal
from flask import Flask, request, jsonify
from flask_cors import CORS
from dataclasses import dataclass
from typing import Optional, Dict, Any
import json
import shutil

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Store active execution sessions
execution_sessions: Dict[str, 'ExecutionSession'] = {}

# Detect if running on Windows
IS_WINDOWS = platform.system() == 'Windows'

@dataclass
class ExecutionSession:
    session_id: str
    process: subprocess.Popen
    input_queue: queue.Queue
    output_queue: queue.Queue
    temp_files: list  # Keep track of temp files for cleanup
    is_waiting_for_input: bool = False
    is_complete: bool = False
    final_output: str = ""
    error_output: str = ""

class CodeExecutor:
    @staticmethod
    def get_file_extension(language: str) -> str:
        extensions = {
            'python': '.py',
            'c': '.c',
            'cpp': '.cpp'
        }
        return extensions.get(language, '.txt')
    
    @staticmethod
    def get_executable_extension() -> str:
        return '.exe' if IS_WINDOWS else '.out'
    
    @staticmethod
    def get_compile_command(filepath: str, language: str, output_path: str) -> Optional[list]:
        if language == 'c':
            if IS_WINDOWS:
                # Try gcc first, then clang
                return ['gcc', filepath, '-o', output_path]
            return ['clang', filepath, '-o', output_path]
        elif language == 'cpp':
            if IS_WINDOWS:
                # Try g++ first, then clang++
                return ['g++', filepath, '-o', output_path]
            return ['clang++', filepath, '-o', output_path]
        return None
    
    @staticmethod
    def get_run_command(filepath: str, language: str, executable_path: str = None) -> list:
        if language == 'python':
            return ['python', filepath]
        elif language in ['c', 'cpp']:
            if IS_WINDOWS:
                # On Windows, we need to run the exe directly
                return [executable_path]
            else:
                # On Unix-like systems
                return [executable_path]
        return []

def cleanup_temp_files(temp_files: list):
    """Clean up temporary files"""
    for filepath in temp_files:
        try:
            if os.path.exists(filepath):
                if os.path.isdir(filepath):
                    shutil.rmtree(filepath)
                else:
                    os.unlink(filepath)
        except Exception as e:
            print(f"Failed to delete {filepath}: {e}")

def output_reader(proc: subprocess.Popen, outq: queue.Queue, session: ExecutionSession):
    """Read output from the process and put it in the queue"""
    try:
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                outq.put(('output', line.rstrip()))
                # Check if the output looks like it's waiting for input
                if any(keyword in line.lower() for keyword in ['input', 'enter', ':', '?']):
                    session.is_waiting_for_input = True
    except Exception as e:
        outq.put(('error', f"Output reader error: {str(e)}"))
    finally:
        try:
            proc.stdout.close()
        except:
            pass

def error_reader(proc: subprocess.Popen, outq: queue.Queue):
    """Read error output from the process"""
    try:
        while True:
            line = proc.stderr.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                outq.put(('error', line.rstrip()))
    except Exception as e:
        outq.put(('error', f"Error reader error: {str(e)}"))
    finally:
        try:
            proc.stderr.close()
        except:
            pass

def input_writer(proc: subprocess.Popen, inq: queue.Queue):
    """Write input to the process when available"""
    while True:
        try:
            input_data = inq.get(timeout=0.1)
            if input_data is None:  # Poison pill
                break
            if proc.poll() is None:  # Process is still running
                proc.stdin.write(input_data + '\n')
                proc.stdin.flush()
        except queue.Empty:
            if proc.poll() is not None:  # Process has ended
                break
            continue
        except Exception as e:
            print(f"Input writer error: {e}")
            break
    
    try:
        proc.stdin.close()
    except:
        pass

@app.route('/execute', methods=['POST'])
def execute_code():
    temp_files = []
    try:
        data = request.json
        code = data.get('code', '')
        language = data.get('language', 'python').lower()
        
        if language not in ['python', 'c', 'cpp']:
            return jsonify({'error': 'Unsupported language'}), 400
        
        # Create a temporary directory for this execution
        temp_dir = tempfile.mkdtemp()
        temp_files.append(temp_dir)
        
        # Create a temporary file for the code
        code_file = os.path.join(temp_dir, f"code{CodeExecutor.get_file_extension(language)}")
        with open(code_file, 'w') as f:
            f.write(code)
        temp_files.append(code_file)
        
        try:
            # Compile if necessary
            executable_path = None
            if language in ['c', 'cpp']:
                executable_path = os.path.join(temp_dir, f"program{CodeExecutor.get_executable_extension()}")
                compile_cmd = CodeExecutor.get_compile_command(
                    code_file, language, executable_path
                )
                
                # Try to compile
                try:
                    compile_result = subprocess.run(
                        compile_cmd,
                        capture_output=True,
                        text=True,
                        timeout=10  # 10 second timeout for compilation
                    )
                except FileNotFoundError:
                    # Compiler not found, try alternative
                    if language == 'c' and IS_WINDOWS:
                        compile_cmd = ['clang', code_file, '-o', executable_path]
                    elif language == 'cpp' and IS_WINDOWS:
                        compile_cmd = ['clang++', code_file, '-o', executable_path]
                    
                    try:
                        compile_result = subprocess.run(
                            compile_cmd,
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                    except FileNotFoundError:
                        cleanup_temp_files(temp_files)
                        return jsonify({
                            'error': 'Compiler not found',
                            'details': f'Please install a C/C++ compiler (gcc/g++ or clang/clang++)'
                        }), 400
                
                if compile_result.returncode != 0:
                    cleanup_temp_files(temp_files)
                    return jsonify({
                        'error': 'Compilation error',
                        'details': compile_result.stderr
                    }), 400
                
                temp_files.append(executable_path)
            
            # Get run command
            run_cmd = CodeExecutor.get_run_command(
                code_file, language, executable_path
            )
            
            # Start the process
            process = subprocess.Popen(
                run_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,  # Unbuffered
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0
            )
            
            # Create session
            session_id = str(uuid.uuid4())
            input_queue = queue.Queue()
            output_queue = queue.Queue()
            
            session = ExecutionSession(
                session_id=session_id,
                process=process,
                input_queue=input_queue,
                output_queue=output_queue,
                temp_files=temp_files
            )
            
            execution_sessions[session_id] = session
            
            # Start threads for I/O handling
            output_thread = threading.Thread(
                target=output_reader,
                args=(process, output_queue, session),
                daemon=True
            )
            error_thread = threading.Thread(
                target=error_reader,
                args=(process, output_queue),
                daemon=True
            )
            input_thread = threading.Thread(
                target=input_writer,
                args=(process, input_queue),
                daemon=True
            )
            
            output_thread.start()
            error_thread.start()
            input_thread.start()
            
            # Wait a bit to see if there's immediate output or if it needs input
            time.sleep(0.3)
            
            # Collect initial output
            initial_output = []
            initial_errors = []
            
            timeout = time.time() + 0.5  # Wait up to 0.5 seconds for initial output
            while time.time() < timeout:
                try:
                    msg_type, msg = output_queue.get_nowait()
                    if msg_type == 'output':
                        initial_output.append(msg)
                    else:
                        initial_errors.append(msg)
                except queue.Empty:
                    if process.poll() is not None:
                        break
                    time.sleep(0.05)
            
            # Check if process has already completed
            if process.poll() is not None:
                # Process completed
                session.is_complete = True
                session.final_output = '\n'.join(initial_output)
                session.error_output = '\n'.join(initial_errors)
                
                # Cleanup
                input_queue.put(None)  # Stop input thread
                cleanup_temp_files(temp_files)
                del execution_sessions[session_id]
                
                return jsonify({
                    'status': 'completed',
                    'output': session.final_output,
                    'error': session.error_output
                })
            
            # Process is still running
            return jsonify({
                'status': 'running',
                'session_id': session_id,
                'output': '\n'.join(initial_output),
                'error': '\n'.join(initial_errors),
                'waiting_for_input': session.is_waiting_for_input or (not initial_output and not initial_errors)
            })
            
        except Exception as e:
            cleanup_temp_files(temp_files)
            raise
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/input', methods=['POST'])
def provide_input():
    try:
        data = request.json
        session_id = data.get('session_id', '')
        user_input = data.get('input', '')
        
        if session_id not in execution_sessions:
            return jsonify({'error': 'Invalid session ID'}), 400
        
        session = execution_sessions[session_id]
        
        if session.process.poll() is not None:
            # Process already terminated
            cleanup_temp_files(session.temp_files)
            del execution_sessions[session_id]
            return jsonify({
                'status': 'completed',
                'output': '',
                'error': 'Process has already terminated'
            })
        
        # Send input to the process
        session.input_queue.put(user_input)
        session.is_waiting_for_input = False
        
        # Wait a bit for output
        time.sleep(0.3)
        
        # Collect output
        output_lines = []
        error_lines = []
        
        timeout = time.time() + 1.0  # Wait up to 1 second for output
        while time.time() < timeout:
            try:
                msg_type, msg = session.output_queue.get_nowait()
                if msg_type == 'output':
                    output_lines.append(msg)
                else:
                    error_lines.append(msg)
            except queue.Empty:
                if session.process.poll() is not None:  # Fixed: was just 'process'
                    break
                time.sleep(0.05)
        
        # Check if process has completed
        if session.process.poll() is not None:
            session.is_complete = True
            
            # Get any remaining output
            while not session.output_queue.empty():
                try:
                    msg_type, msg = session.output_queue.get_nowait()
                    if msg_type == 'output':
                        output_lines.append(msg)
                    else:
                        error_lines.append(msg)
                except queue.Empty:
                    break
            
            session.final_output = '\n'.join(output_lines)
            session.error_output = '\n'.join(error_lines)
            
            # Cleanup
            session.input_queue.put(None)  # Stop input thread
            cleanup_temp_files(session.temp_files)
            del execution_sessions[session_id]
            
            return jsonify({
                'status': 'completed',
                'output': session.final_output,
                'error': session.error_output
            })
        
        # Check if waiting for more input
        session.is_waiting_for_input = False
        if output_lines:
            last_line = output_lines[-1].lower()
            if any(keyword in last_line for keyword in ['input', 'enter', ':', '?']):
                session.is_waiting_for_input = True
        
        return jsonify({
            'status': 'running',
            'output': '\n'.join(output_lines),
            'error': '\n'.join(error_lines),
            'waiting_for_input': session.is_waiting_for_input
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status/<session_id>', methods=['GET'])
def check_status(session_id):
    """Check the status of a running session"""
    try:
        if session_id not in execution_sessions:
            return jsonify({'error': 'Invalid session ID'}), 400
        
        session = execution_sessions[session_id]
        
        # Collect any pending output
        output_lines = []
        error_lines = []
        
        while not session.output_queue.empty():
            try:
                msg_type, msg = session.output_queue.get_nowait()
                if msg_type == 'output':
                    output_lines.append(msg)
                else:
                    error_lines.append(msg)
            except queue.Empty:
                break
        
        # Check if process has completed
        if session.process.poll() is not None:
            session.is_complete = True
            
            # Cleanup
            session.input_queue.put(None)
            cleanup_temp_files(session.temp_files)
            del execution_sessions[session_id]
            
            return jsonify({
                'status': 'completed',
                'output': '\n'.join(output_lines),
                'error': '\n'.join(error_lines)
            })
        
        return jsonify({
            'status': 'running',
            'output': '\n'.join(output_lines),
            'error': '\n'.join(error_lines),
            'waiting_for_input': session.is_waiting_for_input
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/terminate/<session_id>', methods=['POST'])
def terminate_session(session_id):
    """Terminate a running session"""
    try:
        if session_id not in execution_sessions:
            return jsonify({'error': 'Invalid session ID'}), 400
        
        session = execution_sessions[session_id]
        
        # Terminate the process
        if session.process.poll() is None:
            if IS_WINDOWS:
                session.process.terminate()
            else:
                session.process.send_signal(signal.SIGTERM)
            
            # Wait a bit for graceful termination
            try:
                session.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                session.process.kill()
        
        # Cleanup
        session.input_queue.put(None)
        cleanup_temp_files(session.temp_files)
        del execution_sessions[session_id]
        
        return jsonify({'status': 'terminated'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Cleanup any orphaned sessions periodically
def cleanup_old_sessions():
    """Clean up sessions that have been running for too long"""
    while True:
        time.sleep(60)  # Check every minute
        sessions_to_remove = []
        
        for session_id, session in execution_sessions.items():
            if session.process.poll() is not None:
                # Process has terminated
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            session = execution_sessions[session_id]
            cleanup_temp_files(session.temp_files)
            del execution_sessions[session_id]

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_sessions, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True) 
