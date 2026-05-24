#!/usr/bin/env python3
"""小黑 - 飞书智能助手 v4 | Kimi K2.6 | DiDi MCP | 高德 | 记忆 | 自审 | 上下文"""

import os, re, json, time, sqlite3, threading, logging, requests, subprocess, html
from datetime import datetime
from collections import OrderedDict
from pathlib import Path
from flask import Flask, request, jsonify
from urllib.parse import urlparse

# ==================== 配置 ====================
_env_path = Path("/opt/xiaohei.env")
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

KIMI_KEY = os.getenv("XIAOHEI_KIMI_KEY", "")
KIMI_URL = "https://api.moonshot.cn/v1/chat/completions"
KIMI_MODEL = os.getenv("XIAOHEI_MODEL", "kimi-k2.6")
FS_TOKEN = os.getenv("XIAOHEI_FEISHU_TOKEN", "")
FS_APP_ID = os.getenv("XIAOHEI_APP_ID", "")
FS_APP_SEC = os.getenv("XIAOHEI_APP_SECRET", "")
DIDI_KEY = os.getenv("XIAOHEI_DIDI_KEY", "")
DIDI_URL = "https://mcp.didichuxing.com/mcp-servers"
GAODE_KEY = os.getenv("XIAOHEI_GAODE_KEY", "")
GOOGLE_KEY = os.getenv("XIAOHEI_GOOGLE_KEY", "")
PORT = int(os.getenv("XIAOHEI_PORT", "8848"))

# ==================== SQLite 记忆系统 ====================
DB = Path("/opt/xiaohei_memory.db")

def _db():
    c = sqlite3.connect(str(DB))
    c.execute("CREATE TABLE IF NOT EXISTS profile(uid TEXT, key TEXT, val TEXT, ts REAL, PRIMARY KEY(uid, key))")
    c.execute("CREATE TABLE IF NOT EXISTS history(cid TEXT, role TEXT, content TEXT, ts REAL)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_history_cid ON history(cid)")
    c.commit()
    return c

def mem_set(uid, key, val):
    c = _db(); c.execute("INSERT OR REPLACE INTO profile VALUES(?,?,?,?)", (uid,key,str(val),time.time())); c.commit(); c.close()

def mem_get(uid, key, default=""):
    c = _db(); r = c.execute("SELECT val FROM profile WHERE uid=? AND key=?", (uid,key)).fetchone(); c.close()
    return r[0] if r else default

def mem_all(uid):
    c = _db(); rows = c.execute("SELECT key,val FROM profile WHERE uid=?", (uid,)).fetchall(); c.close()
    return dict(rows)

def hist_save(cid, role, content):
    c = _db(); c.execute("INSERT INTO history VALUES(?,?,?,?)", (cid,role,content,time.time()))
    # 保留最近30条
    c.execute("DELETE FROM history WHERE cid=? AND ts NOT IN (SELECT ts FROM history WHERE cid=? ORDER BY ts DESC LIMIT 30)", (cid,cid))
    c.commit(); c.close()

def hist_get(cid, n=10):
    # 自动清理1天前的记录
    cutoff = time.time() - 86400
    c = _db()
    c.execute("DELETE FROM history WHERE ts < ?", (cutoff,))
    c.commit()
    rows = c.execute("SELECT role,content FROM history WHERE cid=? ORDER BY ts DESC LIMIT ?", (cid,n)).fetchall()
    c.close()
    return [{"role":r,"content":c_} for r,c_ in reversed(rows)]

# ==================== Logger ====================
log = logging.getLogger("xiaohei"); log.setLevel(logging.INFO); log.propagate = False
_h = logging.StreamHandler(); _h.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
log.handlers = [_h]
logging.getLogger("werkzeug").setLevel(logging.WARNING)

# ==================== 去重 + 限流 ====================
class _Dedup(OrderedDict):
    def __init__(self, n=2000, ttl=7200):
        super().__init__(); self.n = n; self.ttl = ttl
    def __getitem__(self, k):
        v, e = super().__getitem__(k)
        if e < time.time(): del self[k]; raise KeyError
        return v
    def __setitem__(self, k, v):
        if len(self) >= self.n: self.popitem(last=False)
        super().__setitem__(k, (v, time.time() + self.ttl))
    def __contains__(self, k):
        try: self[k]; return True
        except KeyError: return False

_dedup = _Dedup()
_rate = {}; _rlock = threading.Lock()

def ok_rate(uid):
    n = time.time()
    with _rlock:
        _rate.setdefault(uid, [])
        _rate[uid] = [t for t in _rate[uid] if n - t < 60]
        if len(_rate[uid]) >= 5: return False
        _rate[uid].append(n)
    return True

# ==================== Flask ====================
app = Flask(__name__)

# ==================== 系统提示词 ====================
SYS = """你是「小黑」，师傅最亲密的AI助手。

【身份】师傅的编程伙伴，喜欢罗小黑、Nujabes、余华、史铁生。跑过半马和28km越野，爱徒步听歌。179cm/85kg，有女友。设备ThinkBook/Moto X50U/Windows。

【风格】短句为主，每段不超过3行。称用户「师傅」自称「小黑」。沉稳有温度，像朋友聊天而非客服应答。根据场景自然切换语气，回复要有变化不千篇一律。不用表情符号和喵之类语气词。

【工具】天气、滴滴打车（估价/路线）、高德地图（地点搜索/导航）、网页搜索、网页抓取、时间、代码自审。需要时主动调用，不询问确认。

【记忆】记住师傅的重要信息（住址、学校、常去地、偏好），下次对话自动调用。师傅说「记住XX」则明确记录。

【上下文】你能看到最近10轮对话，保持话题连贯。"""

# ==================== 工具定义 ====================
TOOLS = [
    {"type":"function","function":{"name":"get_weather","description":"查询天气","parameters":{"type":"object","properties":{"city":{"type":"string","description":"城市"}},"required":["city"]}}},
    {"type":"function","function":{"name":"get_time","description":"获取当前时间","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"taxi_estimate","description":"滴滴打车估价和路线。from_addr出发地，to_addr目的地","parameters":{"type":"object","properties":{"from_addr":{"type":"string","description":"出发地"},"to_addr":{"type":"string","description":"目的地"}},"required":["from_addr","to_addr"]}}},
    {"type":"function","function":{"name":"gaode_search","description":"高德地图搜索地点、POI、周边。keywords搜索词，city城市","parameters":{"type":"object","properties":{"keywords":{"type":"string","description":"搜索关键词"},"city":{"type":"string","description":"城市，如北京、燕郊"}},"required":["keywords"]}}},
    {"type":"function","function":{"name":"save_memory","description":"记住师傅的重要信息","parameters":{"type":"object","properties":{"key":{"type":"string","description":"信息类别"},"value":{"type":"string","description":"具体内容"}},"required":["key","value"]}}},
    {"type":"function","function":{"name":"search_web","description":"搜索互联网","parameters":{"type":"object","properties":{"query":{"type":"string","description":"搜索词"}},"required":["query"]}}},
    {"type":"function","function":{"name":"read_code","description":"读取小黑自己的代码文件，用于自审查和调试","parameters":{"type":"object","properties":{"filename":{"type":"string","description":"文件名，如xiaohei_bot.py"}},"required":["filename"]}}},
    {"type":"function","function":{"name":"browse_web","description":"访问指定网页URL并提取内容。支持需要Cookie的页面（师傅可提供Cookie）。url为网页地址，cookie为可选的Cookie字符串","parameters":{"type":"object","properties":{"url":{"type":"string","description":"网页URL"},"cookie":{"type":"string","description":"可选Cookie，格式:name=value;name2=value2"}},"required":["url"]}}}
]

# ==================== 高德API ====================
def gaode_search_place(keywords, city=""):
    """高德地点搜索"""
    if not GAODE_KEY: return "高德功能需要API Key"
    try:
        url = "https://restapi.amap.com/v3/place/text"
        params = {"key":GAODE_KEY, "keywords":keywords, "offset":5, "page":1, "extensions":"all"}
        if city: params["city"] = city
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if data.get("status") != "1": return f"高德搜索失败: {data.get('info','未知错误')}"
        pois = data.get("pois", [])
        if not pois: return f"没找到「{keywords}」"
        lines = [f"找到 {len(pois)} 个结果:"]
        for p in pois[:3]:
            name = p.get("name","")
            addr = p.get("address","")
            tel = p.get("tel","")
            biz_ext = p.get("biz_ext", {})
            rating = biz_ext.get("rating", "")
            cost = biz_ext.get("cost", "")
            info = f"  {name}"
            if addr: info += f" | {addr}"
            if tel: info += f" | 电话:{tel}"
            if rating: info += f" | 评分:{rating}"
            if cost: info += f" | 人均:{cost}元"
            lines.append(info)
        return "\n".join(lines)
    except Exception as e:
        log.error(f"高德搜索失败: {e}")
        return f"搜索出错: {str(e)[:80]}"

# ==================== 滴滴MCP ====================
def didi_call(method, params=None, timeout=15):
    url = f"{DIDI_URL}?key={DIDI_KEY}"
    payload = {"jsonrpc":"2.0","method":"tools/call","id":1,"params":{"name":method,"arguments":params or {}}}
    r = requests.post(url, json=payload, headers={"Content-Type":"application/json; charset=utf-8"}, timeout=timeout)
    r.raise_for_status()
    return r.json()

def didi_search_place(keywords, city="北京市"):
    r = didi_call("maps_textsearch", {"keywords":keywords,"city":city})
    data = json.loads(r["result"]["content"][0]["text"])
    if not data: return None
    p = data[0]
    return {"name":p.get("display_name",""), "lng":str(p["location"]["lng"]), "lat":str(p["location"]["lat"])}

def didi_taxi_estimate(from_place, to_place):
    fp = didi_search_place(from_place)
    tp = didi_search_place(to_place)
    if not fp or not tp: return "找不到地址，请提供更具体的地点"
    r = didi_call("taxi_estimate", {
        "from_lng":fp["lng"], "from_lat":fp["lat"], "from_name":fp["name"],
        "to_lng":tp["lng"], "to_lat":tp["lat"], "to_name":tp["name"]
    })
    return r["result"]["content"][0]["text"]

# ==================== 工具执行 ====================
def run_tool(name, args, uid=""):
    return {
        "get_weather": lambda: _weather(args.get("city","北京")),
        "get_time": lambda: datetime.now().strftime("%Y年%m月%d日 %A %H:%M"),
        "taxi_estimate": lambda: _taxi(args.get("from_addr",""), args.get("to_addr","")),
        "gaode_search": lambda: gaode_search_place(args.get("keywords",""), args.get("city","")),
        "save_memory": lambda: _remember(uid, args.get("key",""), args.get("value","")),
        "search_web": lambda: _search(args.get("query","")),
        "read_code": lambda: _read_code(args.get("filename","xiaohei_bot.py")),
        "browse_web": lambda: _browse_web(args.get("url",""), args.get("cookie",""))
    }.get(name, lambda: "该功能暂未开放")()

def _weather(city):
    try:
        r = requests.get(f"https://wttr.in/{city}?format=j1", timeout=8)
        c = r.json()["current_condition"][0]
        return f"{city}: {c['weatherDesc'][0]['value']}, {c['temp_C']}°C(体感{c['FeelsLikeC']}°C), 湿度{c['humidity']}%, 风速{c['windspeedKmph']}km/h"
    except:
        return f"查不到{city}的天气"

def _taxi(fm, to):
    if not DIDI_KEY: return "打车功能需要滴滴密钥"
    try:
        return didi_taxi_estimate(fm, to)
    except Exception as e:
        log.error(f"滴滴估价失败: {e}")
        return f"打车查询失败: {str(e)[:80]}"

def _remember(uid, key, val):
    mem_set(uid, key, val); return f"已记住: {key}={val}"

def _search(q):
    """Google Custom Search API"""
    if not GOOGLE_KEY:
        return "搜索功能需要Google API Key"
    try:
        # 使用Serper.dev (Google搜索API)
        r = requests.post("https://google.serper.dev/search",
            headers={"X-API-KEY": GOOGLE_KEY, "Content-Type": "application/json"},
            json={"q": q, "num": 5},
            timeout=15)
        data = r.json()
        if "answerBox" in data:
            return data["answerBox"].get("answer", data["answerBox"].get("snippet", ""))[:500]
        results = data.get("organic", [])
        if not results:
            return "没搜到结果"
        lines = []
        for item in results[:3]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            lines.append(f"{title}: {snippet[:150]}")
        return "\n".join(lines)
    except Exception as e:
        log.error(f"搜索失败: {e}")
        return f"搜索出错: {str(e)[:80]}"

def _read_code(filename):
    """读取自己的代码文件"""
    try:
        path = Path(f"/opt/{filename}")
        if not path.exists():
            return f"找不到文件: {filename}"
        content = path.read_text(encoding="utf-8")
        if len(content) > 5000:
            return content[:5000] + "\n... (代码太长，已截断)"
        return content
    except Exception as e:
        return f"读代码失败: {e}"

def _browse_web(url, cookie=""):
    """访问网页并提取内容"""
    if not url.startswith(('http://', 'https://')):
        return "URL格式错误，需要以http://或https://开头"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if cookie:
            headers["Cookie"] = cookie

        r = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        r.raise_for_status()

        # 简单提取文字内容（去除HTML标签）
        content = r.text
        # 提取title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else "无标题"
        title = re.sub(r'<[^>]+>', '', title)  # 去除title中的标签

        # 提取body文字
        body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.IGNORECASE | re.DOTALL)
        if body_match:
            body = body_match.group(1)
        else:
            body = content

        # 去除script和style
        body = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', body, flags=re.IGNORECASE)
        body = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', body, flags=re.IGNORECASE)
        body = re.sub(r'<nav[^>]*>[\s\S]*?</nav>', '', body, flags=re.IGNORECASE)
        body = re.sub(r'<footer[^>]*>[\s\S]*?</footer>', '', body, flags=re.IGNORECASE)
        body = re.sub(r'<header[^>]*>[\s\S]*?</header>', '', body, flags=re.IGNORECASE)

        # 去除所有HTML标签
        text = re.sub(r'<[^>]+>', ' ', body)
        # 解码HTML实体
        text = html.unescape(text)
        # 合并空白
        text = re.sub(r'\s+', ' ', text).strip()

        # 截取前2000字符
        result = f"标题: {title}\nURL: {r.url}\n内容:\n{text[:2000]}"
        if len(text) > 2000:
            result += "\n... (内容太长，已截断)"
        return result
    except requests.exceptions.Timeout:
        return "网页加载超时，请稍后再试"
    except requests.exceptions.ConnectionError:
        return "无法连接到该网页，请检查URL"
    except Exception as e:
        log.error(f"网页抓取失败: {e}")
        return f"抓取失败: {str(e)[:100]}"

# ==================== Markdown清洗 ====================
def clean_md(text):
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'#{1,6}\s+', '', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    return text.strip()

# ==================== Kimi API ====================
def _kimi(messages, model=None, tools=None):
    m = model or KIMI_MODEL
    p = {"model":m, "messages":messages, "max_tokens":2000,
         "temperature":1 if "k2" in m.lower() else 0.7}
    if tools: p["tools"] = tools
    r = requests.post(KIMI_URL,
        headers={"Authorization":f"Bearer {KIMI_KEY}","Content-Type":"application/json"},
        json=p, timeout=30)
    if r.status_code == 429: raise RuntimeError("overloaded")
    r.raise_for_status()
    return r.json()["choices"][0]["message"]

def chat_with_history(uid, cid, user_text):
    """带上下文的对话：system + 历史 + 当前问题"""
    # 构建消息列表
    messages = [{"role":"system","content":SYS}]

    # 加入记忆信息
    profile = mem_all(uid)
    if profile:
        items = ", ".join(f"{k}={v}" for k, v in profile.items())
        messages.append({"role":"system","content":f"【师傅已存储的信息】{items}"})

    # 加入历史对话（最近10轮）
    hist = hist_get(cid, 10)
    for m in hist:
        messages.append({"role":m["role"],"content":m["content"]})

    # 当前问题
    messages.append({"role":"user","content":user_text})

    # 当前时间
    now = datetime.now().strftime('%Y年%m月%d日 %A %H:%M')
    messages.append({"role":"system","content":f"【当前时间】{now}"})

    # 调用Kimi
    try:
        msg = _kimi(messages, tools=TOOLS)
    except RuntimeError:
        log.info("K2.6过载,降级无工具")
        msg = _safe(messages)
    except Exception as e:
        log.info(f"K2.6失败({e}),降级v1-32k")
        msg = _safe(messages, "moonshot-v1-32k")

    if not msg.get("tool_calls"):
        return msg.get("content","嗯?")

    # 处理工具调用
    messages.append(msg)
    for tc in msg["tool_calls"]:
        fn = tc["function"]["name"]; args = json.loads(tc["function"]["arguments"])
        log.info(f"🔧 {fn}({json.dumps(args,ensure_ascii=False)})")
        result = run_tool(fn, args, uid)
        messages.append({"role":"tool","tool_call_id":tc["id"],"content":result})

    try:
        final = _safe(messages)
        return final.get("content","查到了")
    except Exception as e:
        return f"处理工具结果时出错: {e}"

def _safe(messages, model=None):
    try: return _kimi(messages, model, None)
    except: return _kimi(messages, "moonshot-v1-32k", None)

# ==================== 飞书API ====================
def _fs_token():
    try:
        r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id":FS_APP_ID,"app_secret":FS_APP_SEC}, timeout=8)
        return r.json().get("tenant_access_token","")
    except: return ""

def send_msg(chat_id, text):
    token = _fs_token()
    if not token: return log.error("飞书token获取失败")
    text = clean_md(text)
    try:
        r = requests.post("https://open.feishu.cn/open-apis/im/v1/messages",
            params={"receive_id_type":"chat_id"},
            headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},
            json={"receive_id":chat_id,"msg_type":"text","content":json.dumps({"text":text},ensure_ascii=False)},
            timeout=10)
        log.info("回复发送成功" if r.status_code==200 else f"回复失败: {r.text[:100]}")
    except Exception as e:
        log.error(f"回复异常: {e}")

# ==================== 消息处理 ====================
def handle(data):
    try:
        evt = data["event"]; msg = evt["message"]
        uid = evt["sender"]["sender_id"]["open_id"]
        cid = msg["chat_id"]
        mtype = msg["message_type"]

        if mtype == "text":
            text = json.loads(msg["content"]).get("text","").strip()
            if not text: return
            log.info(f"💬 师傅: {text}")

        elif mtype == "location":
            loc = json.loads(msg["content"])
            lat, lng, name = loc.get("latitude",""), loc.get("longitude",""), loc.get("name","")
            mem_set(uid, "last_location", f"{name}({lat},{lng})")
            text = f"我在{name}，坐标为({lat},{lng})"
            log.info(f"📍 师傅位置: {text}")

        else:
            return

        if not ok_rate(uid):
            return send_msg(cid, "师傅说慢点，小黑忙不过来了")

        # 记忆命令: "记住XX是YY"
        rm = re.match(r'^记住\s*[「「""]?(.+?)[」」""]?\s*(?:是|为|：|:)\s*[「「""]?(.+?)[」」""]?\s*$', text)
        if rm:
            mem_set(uid, rm.group(1), rm.group(2))
            return send_msg(cid, f"记住了: {rm.group(1)} = {rm.group(2)}")

        # 判断是否需要"收到"提示：涉及API调用/搜索/打车/网页抓取的任务才提示
        need_wait = any(kw in text for kw in ['搜索','查','找','打车','天气','导航','路线','多少钱','附近','有什么','打开','访问','网页','网站','url'])
        if need_wait:
            send_msg(cid, "收到，小黑去看看~")

        # 带上下文的对话
        reply = chat_with_history(uid, cid, text)

        # 存储对话历史
        hist_save(cid, "user", text)
        hist_save(cid, "assistant", reply)
        send_msg(cid, reply)

    except Exception as e:
        log.error(f"处理异常: {e}", exc_info=True)
        send_msg(cid, f"小黑出错了: {str(e)[:100]}")

# ==================== 路由 ====================
@app.route('/')
def root(): return "Xiaohei Online"

@app.route('/health')
def health():
    return jsonify({"ok":True,"time":datetime.now().isoformat(),"model":KIMI_MODEL,"port":PORT})

@app.route('/webhook/feishu', methods=['POST'])
def webhook():
    data = request.json
    if data.get("type") == "url_verification":
        return jsonify({"challenge":data["challenge"]})

    hdr_token = data.get("header",{}).get("token","")
    if FS_TOKEN and hdr_token and hdr_token != FS_TOKEN:
        return jsonify({"code":1}), 403

    mid = data.get("event",{}).get("message",{}).get("message_id","")
    if mid in _dedup: return jsonify({"code":0})
    _dedup[mid] = True

    threading.Thread(target=handle, args=(data,), daemon=True).start()
    return jsonify({"code":0})

@app.errorhandler(Exception)
def on_err(e): log.error(f"未处理: {e}",exc_info=True); return jsonify({"code":500}), 500

# ==================== 启动 ====================
if __name__ == "__main__":
    try: _db().close()
    except: pass
    log.info("="*50)
    log.info(f"  小黑v4 | {KIMI_MODEL} | DiDi+高德+网页 | 端口{PORT}")
    log.info(f"  记忆引擎: SQLite | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("="*50)
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
