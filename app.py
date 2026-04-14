import socket
import threading
import json
from datetime import datetime
import os
from flask import Flask, render_template, request, jsonify

# ===== CONFIG =====
BROADCAST_PORT = 9999
HIST_DIR = "historicos"

if not os.path.exists(HIST_DIR):
    os.mkdir(HIST_DIR)

app = Flask(__name__)

PORT_POOL = set(range(5001, 5100))  # Define um intervalo de portas (ex: 5001 a 5099)
usuarios_ativos = {}  # {nome: {"porta": 5001, "last_seen": timestamp}}

registro_portas_fixas = {} 
PORT_POOL = list(range(5001, 5100))

@app.route("/solicitar_porta", methods=["POST"])
def solicitar_porta():
    data = request.json
    nome = data.get("nome")
    
    if not nome:
        return jsonify({"status": "erro", "msg": "Nome necessário"}), 400

    # 1. Verifica se o usuário já tem uma porta atribuída anteriormente
    if nome in registro_portas_fixas:
        porta = registro_portas_fixas[nome]
    else:
        # 2. Se for novo, atribui a próxima porta disponível do pool
        portas_ocupadas = set(registro_portas_fixas.values())
        portas_disponiveis = [p for p in PORT_POOL if p not in portas_ocupadas]
        
        if not portas_disponiveis:
            return jsonify({"status": "erro", "msg": "Limite de usuários atingido"}), 507
            
        porta = portas_disponiveis[0]
        registro_portas_fixas[nome] = porta

    # 3. Atualiza o status de atividade (mesmo que a porta seja a mesma)
    usuarios_ativos[nome] = {
        "porta": porta,
        "last_seen": datetime.now()
    }
    
    return jsonify({"status": "ok", "porta": porta})

# A função limpar_usuarios_inativos remove apenas de 'usuarios_ativos' 
# para liberar espaço visual na lista, mas o 'registro_portas_fixas' 
# mantém a reserva da porta para aquele nome.
def limpar_usuarios_inativos():
    agora = datetime.now()
    para_remover = [nome for nome, d in usuarios_ativos.items() 
                    if (agora - d["last_seen"]).total_seconds() > 20]
    for nome in para_remover:
        del usuarios_ativos[nome]

@app.route("/keep_alive", methods=["POST"])
def keep_alive():
    nome = request.json.get("nome")
    if nome in usuarios_ativos:
        usuarios_ativos[nome]["last_seen"] = datetime.now()
    return jsonify({"status": "ok"})

def limpar_usuarios_inativos():
    agora = datetime.now()
    para_remover = []
    for nome, dados in usuarios_ativos.items():
        # Se não houver sinal de vida por mais de 15 segundos, libera a porta
        if (agora - dados["last_seen"]).total_seconds() > 15:
            para_remover.append(nome)
    
    for nome in para_remover:
        del usuarios_ativos[nome]

send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
broadcast_send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
broadcast_send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

vizinhos = {}
historicos = {}

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except:
        return "127.0.0.1"
    finally:
        s.close()

IP_LOCAL = get_ip()

def salvar(nome_usuario):
    with open(f"{HIST_DIR}/historico_{nome_usuario}.json", "w") as f:
        json.dump(historicos.get(nome_usuario, {}), f)

def carregar(nome_usuario):
    path = f"{HIST_DIR}/historico_{nome_usuario}.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            historicos[nome_usuario] = json.load(f)
    else:
        historicos[nome_usuario] = {}

# ===== UDP Threads =====
def anunciar(nome, porta):
    while True:
        msg = {"tipo": "discover", "nome": nome, "ip": IP_LOCAL, "porta": porta}
        broadcast_send_sock.sendto(json.dumps(msg).encode(), ('255.255.255.255', BROADCAST_PORT))
        threading.Event().wait(5)

def ouvir_broadcast(meu_nome):
    sock_b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_b.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_b.bind(('', BROADCAST_PORT))
    while True:
        data, addr = sock_b.recvfrom(4096)
        try:
            msg = json.loads(data.decode())
            if msg["nome"] != meu_nome:
                vizinhos[msg["nome"]] = {"ip": msg["ip"], "porta": int(msg["porta"])}
        except: pass

def receber_mensagens(porta_udp, meu_nome):
    sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_recv.bind(('', int(porta_udp)))
    while True:
        data, addr = sock_recv.recvfrom(4096)
        try:
            msg = json.loads(data.decode())
            origem = msg["remetente"]["nome"]
            texto = msg["conteudo"]
            hora = msg["timestamp"]

            if msg.get("encaminhado"):
                comentario = msg.get("comentario", "")
                prefixo = f"🔁 Encaminhado: \"{texto}\""
                texto = f"{prefixo}\nNota: {comentario}" if comentario else prefixo

            historicos.setdefault(meu_nome, {}).setdefault(origem, []).append({"remetente": origem, "texto": texto, "hora": hora})
            salvar(meu_nome)
        except: pass

# ===== Flask Routes =====
@app.route("/")
def index(): return render_template("index.html")

@app.route("/init", methods=["POST"])
def init():
    data = request.json
    nome, porta = data["nome"], int(data["porta"])
    carregar(nome)
    threading.Thread(target=receber_mensagens, args=(porta, nome), daemon=True).start()
    threading.Thread(target=anunciar, args=(nome, porta), daemon=True).start()
    threading.Thread(target=ouvir_broadcast, args=(nome,), daemon=True).start()
    return jsonify({"status": "ok"})

@app.route("/vizinhos/<nome>")
def get_vizinhos(nome): return jsonify(list(vizinhos.keys()))

@app.route("/historico/<nome>")
def get_historico(nome): return jsonify(historicos.get(nome, {}))

@app.route("/enviar", methods=["POST"])
def enviar():
    data = request.json
    remetente, dest_nome, texto = data["remetente"], data["destinatario"], data["conteudo"]
    encaminhado = data.get("encaminhado", False)
    comentario = data.get("comentario", "")

    v = vizinhos.get(dest_nome)
    if not v: return jsonify({"status": "erro", "msg": "Offline"})

    msg = {
        "timestamp": datetime.now().strftime("%H:%M"),
        "remetente": {"nome": remetente, "ip": IP_LOCAL},
        "conteudo": texto,
        "encaminhado": encaminhado,
        "comentario": comentario
    }
    send_sock.sendto(json.dumps(msg).encode(), (v["ip"], v["porta"]))
    
    # Histórico Local
    display_text = texto
    if encaminhado:
        display_text = f"🔁 Encaminhado: \"{texto}\"" + (f"\nNota: {comentario}" if comentario else "")
    
    historicos.setdefault(remetente, {}).setdefault(dest_nome, []).append({"remetente": "EU", "texto": display_text, "hora": msg["timestamp"]})
    salvar(remetente)
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)