import json

log_path = '/home/manchax/.gemini/antigravity-ide/brain/266ea80e-a005-45e4-825a-e796ea95d128/.system_generated/logs/transcript.jsonl'
with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        if data.get("step_index") == 62:
            code = data["tool_calls"][0]["args"]["CodeContent"]
            with open("app/services/hpn_agents.py", "w", encoding="utf-8") as out:
                out.write(code)
            print("hpn_agents.py recuperado exitosamente!")
            break
