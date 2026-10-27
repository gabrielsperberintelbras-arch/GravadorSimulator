import os, sys, time, importlib.util
os.environ["DISPLAY"] = ":99"
os.environ["SIMULADOR_GRAVADOR_CONFIG"] = "/tmp/grav_cfg_test.json"
if os.path.exists("/tmp/grav_cfg_test.json"): os.remove("/tmp/grav_cfg_test.json")
spec = importlib.util.spec_from_file_location("grav", "/home/claude/gravador_simulator.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import tkinter as tk
root = tk.Tk(); root.geometry("1240x800+0+0")
app = m.GravadorSimulator(root)
def pump(ms=50):
    end = time.time() + ms/1000
    while time.time() < end:
        root.update(); time.sleep(0.005)
pump(200)
fails = 0
def check(name, got, exp):
    global fails
    ok = got == exp
    if not ok: fails += 1
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n   got={got!r}\n   exp={exp!r}"))
def reset(**cfg):
    app.cfg = dict(m.DEFAULT_CFG); app.cfg.update(cfg)
    app.txn_lines=[]; app.rx_buf=b""; app.last_data_mono=None; app.view_page=None; app.txn_done=False
    app._warned_flush=False; app._last_bad_warn=0
    app.log_text.configure(state="normal"); app.log_text.delete("1.0","end"); app.log_text.configure(state="disabled")
def log_text():
    pump(30); return app.log_text.get("1.0","end")

reset(); app._on_data(b"LOJA\r\nCNPJ\r\n","t")
check("CRLF um pacote", (app.txn_lines, app.rx_buf), (["LOJA","CNPJ"], b""))
reset(); [app._on_data(c,"t") for c in (b"LOJ", b"A\r\nTOT", b"AL\r\n")]
check("fragmentado TCP", (app.txn_lines, app.rx_buf), (["LOJA","TOTAL"], b""))
reset(); [app._on_data(c,"t") for c in (b"AB\r", b"\nCD\r\n")]
check("CR|LF separados", app.txn_lines, ["AB","CD"])
reset(); app._on_data(b"A\nB\nC\n","t")
check("LF puro", app.txn_lines, ["A","B","C"])
reset(); app._on_data(b"A\rB\rC\r","t"); pump(600)
check("CR puro + flush", app.txn_lines, ["A","B","C"])
reset(); app._on_data(b"HELLO","t"); check("sem terminador (antes)", app.txn_lines, []); pump(600)
check("sem terminador (flush)", app.txn_lines, ["HELLO"])
check("aviso de terminador", "sem terminador" in log_text(), True)
reset(quebra="|"); app._on_data(b"A|B|C|","t")
check("quebra customizada |", app.txn_lines, ["A","B","C"])
reset(quebra="\\r\\n"); app._on_data(b"X\r\nY\r\n","t")
check("quebra \\r\\n digitada", app.txn_lines, ["X","Y"])
reset(); app._on_data("AÇÚCAR\r\n".encode("latin-1"),"t")
check("latin1 lido como utf8 => \\ufffd", "\ufffd" in app.txn_lines[0], True)
check("aviso de codificacao", "Caracteres inválidos" in log_text(), True)
reset(converter="Latin-1 (ISO-8859-1)"); app._on_data("AÇÚCAR\r\n".encode("latin-1"),"t")
check("latin1 com Converter correto", app.txn_lines, ["AÇÚCAR"])
reset(); app._on_data("AÇÚCAR\r\n".encode("utf-8"),"t")
check("utf8 com Converter UTF-8", app.txn_lines, ["AÇÚCAR"])
reset(protocolo="POSUTF8", converter="ASCII"); app._on_data("AÇÚCAR\r\n".encode("utf-8"),"t")
check("POSUTF8 forca UTF-8", app.txn_lines, ["AÇÚCAR"])
reset(privacy=["CARTAO","",""]); app._on_data(b"FORMA DE PAGAMENTO: CARTAO DEBITO 1234\r\nTOTAL 10,00\r\n","t")
check("privacidade mascara depois da palavra", app.txn_lines, ["FORMA DE PAGAMENTO: CARTAO ****** ****","TOTAL 10,00"])
reset(fonte="Grande"); app._on_data(("".join(f"LINHA {i:02d}\r\n" for i in range(30))).encode(),"t")
vis, idx, n = app._page_info()
check("pagina: varias paginas", n > 1 and idx == n-1, True)
app._page_prev(); _, idx2, _ = app._page_info()
check("◀ volta uma pagina", idx2, idx-1)
app._page_next(); _, idx3, _ = app._page_info()
check("▶ volta a seguir a ultima", idx3, idx)
reset(fonte="Pequeno"); app._on_data(("".join(f"LINHA {i:02d}\r\n" for i in range(30))).encode(),"t")
_,_,n_small = app._page_info()
reset(fonte="Grande"); app._on_data(("".join(f"LINHA {i:02d}\r\n" for i in range(30))).encode(),"t")
_,_,n_big = app._page_info()
check("fonte menor => menos paginas", n_small < n_big, True)
reset(sobrepor="Lista"); app._on_data(("".join(f"LINHA {i:02d}\r\n" for i in range(30))).encode(),"t")
vis, idx, n = app._page_info()
check("lista: ultima linha visivel e 1 pagina", (vis[-1], n), ("LINHA 29", 1))
reset(); app._on_data(("PALAVRA "*40+"\r\n").encode(),"t")
font, rows, lh, cap = app._overlay_rows()
check("linha longa quebra em varias linhas de tela", len(rows) > 1, True)
reset(timeout=5); app._on_data(b"VENDA 1\r\n","t"); app.last_data_mono -= 10
app._on_data(b"VENDA 2\r\n","t")
check("tempo excedido inicia nova venda", app.txn_lines, ["VENDA 2"])
reset(display=5); app._on_data(b"VENDA\r\n","t"); app.last_data_mono -= 10; app._tick()
check("tempo de exibicao oculta overlay", app.txn_lines, [])
reset(sinal="Muito Obrigado!"); app._on_data(b"A\r\nMuito Obrigado!\r\n","t"); app._on_data(b"B\r\n","t")
check("sinal final => proxima venda limpa", app.txn_lines, ["B"])
app.stat_packets=app.stat_bytes=app.stat_lines=0; reset(); app._on_data(b"A\r\nB\r\n","t")
check("estatisticas", (app.stat_packets, app.stat_bytes, app.stat_lines), (1, 6, 2))
app.v_porta.set("99999")
try: app._collect_ui(strict=True); ok=False
except ValueError: ok=True
check("porta invalida rejeitada", ok, True)
app.v_porta.set("9000"); app.v_ip.set("300.1.1.1")
try: app._collect_ui(strict=True); ok=False
except ValueError: ok=True
check("IP invalido rejeitado", ok, True)
print("\nRESULTADO:", "TUDO OK" if fails == 0 else f"{fails} FALHA(S)")
root.destroy()
