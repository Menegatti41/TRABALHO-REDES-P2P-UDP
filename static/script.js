let selecionada = null;
let nomeAtual = "";
let usuarioSelecionado = "";

async function iniciar() {
    nomeAtual = document.getElementById("nome").value.trim();
    if(!nomeAtual) return alert("Digite seu nome!");

    const response = await fetch("/solicitar_porta", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ nome: nomeAtual })
    });
    
    const resData = await response.json();
    if(resData.status === "ok") {
        const portaFixa = resData.porta;

        // Reinicia os sockets no backend para esta porta específica
        fetch("/init", {
            method: "POST", 
            headers: {"Content-Type": "application/json"}, 
            body: JSON.stringify({ nome: nomeAtual, porta: portaFixa })
        });

        // Interface
        document.getElementById("status").innerText = `Sua Porta Fixa: ${portaFixa}`;
        document.querySelector(".login-bar").style.display = "none"; // Esconde login após entrar
        
        if(resData.status === "ok") {
        document.getElementById("meu-nome-display").innerText = nomeAtual;
        document.getElementById("meu-avatar").innerText = nomeAtual[0].toUpperCase();
        document.querySelector(".login-bar").style.display = "none";
    
    iniciarLoops();
}
        // Loops
        iniciarLoops();
    }
}

function iniciarLoops() {
    setInterval(atualizarVizinhos, 2000);
    setInterval(atualizarChat, 1000);
    setInterval(() => {
        fetch("/keep_alive", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ nome: nomeAtual })
        });
    }, 5000);
}

function atualizarVizinhos() {
    fetch(`/vizinhos/${nomeAtual}`).then(r => r.json()).then(data => {
        const lista = document.getElementById("lista-usuarios");
        lista.innerHTML = "";

        data.forEach(v => {
            const item = document.createElement("div");
            item.className = `user-item ${v === usuarioSelecionado ? 'active' : ''}`;
            item.innerHTML = `
                <div class="user-avatar">${v[0].toUpperCase()}</div>
                <div class="user-info"><strong>${v}</strong></div>
            `;
            item.onclick = () => selecionarUsuario(v);
            lista.appendChild(item);
        });
    });
}

function selecionarUsuario(nome) {
    usuarioSelecionado = nome;
    document.getElementById("chat-com-titulo").innerText = `Conversando com: ${nome}`;
    atualizarVizinhos(); // Atualiza a classe 'active' na lista
    atualizarChat();     // Força recarga das mensagens
}

function atualizarChat() {
    if(!usuarioSelecionado) return;

    fetch(`/historico/${nomeAtual}`).then(r => r.json()).then(data => {
        const chat = document.getElementById("chat");
        const msgs = data[usuarioSelecionado] || [];

        if(chat.children.length !== msgs.length) {
            chat.innerHTML = "";
            msgs.forEach((m, i) => {
                const div = document.createElement("div");
                div.className = `message ${m.remetente === "EU" ? "EU" : "OTHER"}`;
                div.innerHTML = `<div>${m.texto}</div><span class="time">${m.hora}</span>`;
                div.onclick = () => prepararEncaminhamento(m, div);
                chat.appendChild(div);
            });
            chat.scrollTop = chat.scrollHeight;
        }
    });
}

function prepararEncaminhamento(msgObj, element) {
    // Remove seleção anterior
    document.querySelectorAll('.message').forEach(m => m.classList.remove('selected'));
    
    selecionada = msgObj;
    element.classList.add('selected');
    
    document.getElementById("fw-msg-preview").innerText = `Encaminhando: "${msgObj.texto}"`;
    document.getElementById("panel-encaminhar").style.display = "flex";
}

function confirmarEncaminhamento() {
    const comentario = document.getElementById("msg-comentario").value;
    
    if(!selecionada || !usuarioSelecionado) {
        alert("Selecione para quem deseja encaminhar na lista lateral!");
        return;
    }

    fetch("/enviar", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            remetente: nomeAtual,
            destinatario: usuarioSelecionado,
            conteudo: selecionada.texto,
            encaminhado: true,
            comentario: comentario
        })
    }).then(() => {
        cancelarEncaminhamento();
        atualizarChat(); 
    });
}

function cancelarEncaminhamento() {
    selecionada = null;
    document.querySelectorAll('.message').forEach(m => m.classList.remove('selected'));
    document.getElementById("panel-encaminhar").style.display = "none";
    document.getElementById("msg-comentario").value = "";
}

function enviarMensagem(){
    const txt = document.getElementById("mensagem").value;
    if(!txt || !usuarioSelecionado) {
        alert("Selecione um usuário na lista lateral para conversar!");
        return;
    }

    fetch("/enviar", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            remetente: nomeAtual, 
            destinatario: usuarioSelecionado, 
            conteudo: txt
        })
    });
    document.getElementById("mensagem").value = "";
}

function handleKey(e) { if(e.key === "Enter") enviarMensagem(); }