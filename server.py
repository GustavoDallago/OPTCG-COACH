import http.server
import socketserver
import webbrowser

DEFAULT_PORT = 8000
MAX_PORT_ATTEMPTS = 10
Handler = http.server.SimpleHTTPRequestHandler

class MyHandler(Handler):
    def end_headers(self):
        # Disable cache to avoid stale responses during testing
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        super().end_headers()

def main():
    httpd = None
    selected_port = DEFAULT_PORT
    
    # Try finding an open port starting from 8000 (Item 7)
    for port in range(DEFAULT_PORT, DEFAULT_PORT + MAX_PORT_ATTEMPTS):
        try:
            httpd = socketserver.TCPServer(("", port), MyHandler)
            selected_port = port
            break
        except OSError:
            print(f"Porta {port} ocupada, tentando a próxima...")

    if not httpd:
        print("❌ Erro: Não foi possível vincular o servidor a nenhuma porta no intervalo 8000-8009.")
        print("Por favor, feche outras aplicações que estejam utilizando essas portas e tente novamente.")
        return

    url = f"http://localhost:{selected_port}"
    print("==================================================")
    print(f" Servidor Local OPTCG Visualizer Ativo!")
    print(f" Acesse em seu navegador: {url}")
    print(" Pressione Ctrl+C no terminal para encerrar.")
    print("==================================================")
    
    webbrowser.open(url)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor finalizado pelo usuário.")
    finally:
        httpd.server_close()

if __name__ == "__main__":
    main()
