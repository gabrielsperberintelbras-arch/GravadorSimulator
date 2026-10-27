import os, time, socket, subprocess, importlib.util, threading
os.environ["DISPLAY"] = ":99"
os.environ["SIMULADOR_GRAVADOR_CONFIG"] = "/tmp/grav_cfg_net.json"
if os.path.exists("/tmp/grav_cfg_net.json"): os.remove("/tmp/grav_cfg_net.json")
spec = importlib.util.spec_from_file_location("grav", "/home/claude/gravador_simulator.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import tkinter as tk
root = tk.Tk(); root.geometry("1240x800+0+0")
app = m.GravadorSimulator(root)
def pump(ms):
    end = time.time()+ms/1000
    while time.time()<end: root.update(); time.sleep(0.005)
def wait(cond, ms=4000):
    end=time.time()+ms/1000
    while time.time()<end:
        root.update()
        if cond(): return True
        time.sleep(0.01)
    return False
fails=0
def check(n, ok, extra=""):
    global fails
    if not ok: fails+=1
    print(("PASS " if ok else "FAIL ")+n+(" "+extra if not ok else ""))
LINES=["LOJA TESTE","CNPJ 00.000.000/0001-00","AÇÚCAR REFINADO 1KG 2x4,80 ... 9,60","FORMA DE PAGAMENTO: CARTAO DEBITO 1234","Muito Obrigado!"]
def pdv_send_lines(send):               # igual ao PDV: linha + CRLF, utf-8, com atraso
    for l in LINES:
        send((l+"\r\n").encode("utf-8")); time.sleep(0.05)
def clear():
    app._clear_screen(); app.stat_packets=app.stat_bytes=app.stat_lines=0
def setcfg(modo, port, **kw):
    label=[k for k,v in m.MODES.items() if v==modo][0]
    app.v_modo.set(label); app.v_ip.set("127.0.0.1" if modo=="TCP_CLIENT" else "0.0.0.0"); app.v_porta.set(str(port))
    app.v_priv[0].set("CARTAO")
    for k,v in kw.items(): getattr(app,k).set(v)

# ---- 1) gravador TCP (escuta) <-> PDV "TCP Cliente"
setcfg("TCP", 19101); app.enable_toggle.set(True, fire=True)
check("TCP: escutando", wait(lambda: "ESCUTANDO" in app.status_var.get()), app.status_var.get())
c = socket.create_connection(("127.0.0.1",19101)); 
check("TCP: PDV conectou", wait(lambda: "CONECTADO" in app.status_var.get()), app.status_var.get())
pdv_send_lines(c.sendall)
check("TCP: 5 linhas recebidas", wait(lambda: app.stat_lines==5), str(app.txn_lines))
check("TCP: privacidade+utf8", app.txn_lines[3]=="FORMA DE PAGAMENTO: CARTAO ****** ****" and app.txn_lines[2].startswith("AÇÚCAR"), str(app.txn_lines))
pump(300)
subprocess.run(["import","-window","root","/home/claude/shots/grav_tcp.png"])
c.close()
check("TCP: detecta desconexao", wait(lambda: "ESCUTANDO" in app.status_var.get()), app.status_var.get())
c2 = socket.create_connection(("127.0.0.1",19101)); clear()      # reconexao do PDV
c2.sendall("NOVA VENDA\r\n".encode()); 
check("TCP: aceita nova conexao", wait(lambda: app.txn_lines==["NOVA VENDA"]), str(app.txn_lines)); c2.close()
app.enable_toggle.set(False, fire=True); pump(200)
t=socket.socket(); t.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
try: t.bind(("0.0.0.0",19101)); t.listen(1); ok=True
except OSError: ok=False
t.close(); check("TCP: desabilitar libera a porta", ok and "DESABILITADO" in app.status_var.get(), app.status_var.get())

# ---- 2) gravador UDP <-> PDV "UDP"
clear(); setcfg("UDP", 19102); app.enable_toggle.set(True, fire=True)
check("UDP: escutando", wait(lambda: "UDP ESCUTANDO" in app.status_var.get()), app.status_var.get())
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
pdv_send_lines(lambda b: u.sendto(b, ("127.0.0.1",19102)))
check("UDP: 5 linhas recebidas", wait(lambda: app.stat_lines==5), str(app.txn_lines))
pdv_all = "".join(l+"\r\n" for l in LINES).encode(); clear()     # "Enviar tudo (1 pacote)"
u.sendto(pdv_all, ("127.0.0.1",19102))
check("UDP: pacote unico com 5 linhas", wait(lambda: app.stat_lines==5 and app.stat_packets==1), f"{app.stat_lines} {app.stat_packets}")
app.enable_toggle.set(False, fire=True)

# ---- 3) gravador TCP_CLIENT (conecta) <-> PDV "TCP Servidor"
clear(); setcfg("TCP_CLIENT", 19103); app.enable_toggle.set(True, fire=True)
pump(500)
lg=app.log_text.get("1.0","end")
check("TCP_CLIENT: sem PDV => erro claro + retry", "Conexão recusada pelo PDV" in lg and "Tentando de novo" in lg and "reconectando" in app.status_var.get().lower(), lg[-300:])
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1); srv.bind(("127.0.0.1",19103)); srv.listen(1); srv.settimeout(6)
conn,_ = srv.accept()
check("TCP_CLIENT: conectou no PDV ao subir", wait(lambda: "CONECTADO AO PDV" in app.status_var.get()), app.status_var.get())
pdv_send_lines(conn.sendall)
check("TCP_CLIENT: 5 linhas recebidas", wait(lambda: app.stat_lines==5), str(app.txn_lines))
conn.close()
check("TCP_CLIENT: PDV caiu => aviso", wait(lambda: "encerrada" in app.log_text.get("1.0","end")))
conn,_ = srv.accept()                                              # gravador reconecta sozinho
check("TCP_CLIENT: reconectou sozinho", True); clear()
conn.sendall(b"DEPOIS DA QUEDA\r\n")
check("TCP_CLIENT: dados apos reconexao", wait(lambda: app.txn_lines==["DEPOIS DA QUEDA"]), str(app.txn_lines))
conn.close(); srv.close()
app.enable_toggle.set(False, fire=True)

# ---- 4) filtro de IP de origem
clear(); setcfg("UDP", 19104, v_ip_origem="10.9.9.9"); app.enable_toggle.set(True, fire=True)
wait(lambda: "UDP ESCUTANDO" in app.status_var.get())
u.sendto(b"BLOQUEADO\r\n", ("127.0.0.1",19104)); pump(400)
check("filtro de origem descarta IP diferente", app.txn_lines==[] and app.stat_packets==0, str(app.txn_lines))
app.enable_toggle.set(False, fire=True)

# ---- 5) porta ocupada => erro amigavel (sem abrir messagebox bloqueante)
import tkinter.messagebox as mb; shown=[]; mb.showerror=lambda t,msg: shown.append((t,msg))
m.messagebox.showerror = mb.showerror
blk = socket.socket(); blk.bind(("0.0.0.0",19105)); blk.listen(1)
setcfg("TCP", 19105); app.v_ip_origem.set(""); app.enable_toggle.set(True, fire=True)
check("porta em uso: erro amigavel", wait(lambda: shown and "porta" in shown[0][0].lower()), str(shown))
check("porta em uso: toggle volta a OFF", app.enable_toggle.get() is False)
blk.close()
print("\nRESULTADO:", "TUDO OK" if fails==0 else f"{fails} FALHA(S)")
app._stop_net(silent=True); root.destroy()
