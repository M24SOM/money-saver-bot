# health_check.py
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    server = HTTPServer(('0.0.0.0', 8000), HealthCheckHandler)
    server.serve_forever()

# In your bot.py (or main script)
if __name__ == "__main__":
    import threading
    from health_check import start_health_server

    threading.Thread(target=start_health_server, daemon=True).start()

    # Then start your bot logic
    from telegram.ext import ApplicationBuilder
    # Your bot setup here...
