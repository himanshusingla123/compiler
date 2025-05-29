# client_example.py (Complete updated version)
import requests
import json
import time

BASE_URL = "http://localhost:5000"

def test_python_code():
    """Test Python code with input"""
    print("Testing Python code with input...")
    
    code = """
name = input("Enter your name: ")
age = input("Enter your age: ")
print(f"Hello {name}, you are {age} years old!")
"""
    
    # Execute code
    response = requests.post(f"{BASE_URL}/execute", json={
        "code": code,
        "language": "python"
    })
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    print(f"Initial response: {json.dumps(result, indent=2)}")
    
    if 'error' in result and result['error']:
        print(f"Execution error: {result['error']}")
        if 'details' in result:
            print(f"Details: {result['details']}")
        return
    
    if result.get('status') == 'running':
        session_id = result['session_id']
        
        # Provide first input
        response = requests.post(f"{BASE_URL}/input", json={
            "session_id": session_id,
            "input": "John"
        })
        result = response.json()
        print(f"After first input: {json.dumps(result, indent=2)}")
        
        if result.get('status') == 'running':
            # Provide second input
            response = requests.post(f"{BASE_URL}/input", json={
                "session_id": session_id,
                "input": "25"
            })
            result = response.json()
            print(f"Final output: {json.dumps(result, indent=2)}")

def test_cpp_code():
    """Test C++ code with input"""
    print("\nTesting C++ code with input...")
    
    code = """
#include <iostream>
#include <string>
using namespace std;

int main() {
    string name;
    int num1, num2;
    
    cout << "Enter your name: ";
    cin >> name;
    
    cout << "Enter first number: ";
    cin >> num1;
    
    cout << "Enter second number: ";
    cin >> num2;
    
    cout << "Hello " << name << "!" << endl;
    cout << "The sum of " << num1 << " and " << num2 << " is " << (num1 + num2) << endl;
    
    return 0;
}
"""
    
    # Execute code
    response = requests.post(f"{BASE_URL}/execute", json={
        "code": code,
        "language": "cpp"
    })
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    print(f"Initial response: {json.dumps(result, indent=2)}")
    
    if 'error' in result and result['error']:
        print(f"Execution error: {result['error']}")
        if 'details' in result:
            print(f"Details: {result['details']}")
        return
    
    if result.get('status') == 'running':
        session_id = result['session_id']
        
        # Provide inputs
        inputs = ["Alice", "10", "20"]
        for inp in inputs:
            time.sleep(0.5)  # Small delay between inputs
            response = requests.post(f"{BASE_URL}/input", json={
                "session_id": session_id,
                "input": inp
            })
            result = response.json()
            print(f"After input '{inp}': {json.dumps(result, indent=2)}")
            
            if result.get('status') == 'completed':
                break

def test_c_code():
    """Test C code with input"""
    print("\nTesting C code with input...")
    
    code = """
#include <stdio.h>

int main() {
    char name[100];
    int age;
    
    printf("What is your name? ");
    scanf("%s", name);
    
    printf("How old are you? ");
    scanf("%d", &age);
    
    printf("\\nHello %s!\\n", name);
    printf("In 10 years, you will be %d years old.\\n", age + 10);
    
    return 0;
}
"""
    
    # Execute code
    response = requests.post(f"{BASE_URL}/execute", json={
        "code": code,
        "language": "c"
    })
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    print(f"Initial response: {json.dumps(result, indent=2)}")
    
    if 'error' in result and result['error']:
        print(f"Execution error: {result['error']}")
        if 'details' in result:
            print(f"Details: {result['details']}")
        return
    
    if result.get('status') == 'running':
        session_id = result['session_id']
        
        # Provide inputs
        inputs = ["Bob", "30"]
        for inp in inputs:
            time.sleep(0.5)
            response = requests.post(f"{BASE_URL}/input", json={
                "session_id": session_id,
                "input": inp
            })
            result = response.json()
            print(f"After input '{inp}': {json.dumps(result, indent=2)}")
            
            if result.get('status') == 'completed':
                break

def test_simple_python():
    """Test simple Python code without input"""
    print("\nTesting simple Python code without input...")
    
    code = """
print("Hello, World!")
for i in range(5):
    print(f"Count: {i}")
print("Done!")
"""
    
    response = requests.post(f"{BASE_URL}/execute", json={
        "code": code,
        "language": "python"
    })
    
    result = response.json()
    print(f"Result: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    # Test all scenarios
    test_simple_python()
    test_python_code()
    test_cpp_code()
    test_c_code()