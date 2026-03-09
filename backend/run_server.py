import uvicorn
import os
import sys
import socket

def find_free_port(start_port: int = 8000, max_tries: int = 10) -> int:
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    return start_port

def launch():
    # Force 8001 if possible to match existing UI expectations
    port = find_free_port(8001)
    print(f"🚀 Found free port: {port}")
    
    # Save the port so Gradio can find us (Gradio looks in root)
    # The script is in backend/run_server.py, so root is one level up
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    port_file = os.path.join(root_dir, ".port")
    print(f"📍 Writing port to: {port_file}")
    with open(port_file, "w") as f:
        f.write(str(port))
    
    # Run uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)

if __name__ == "__main__":
    launch()
