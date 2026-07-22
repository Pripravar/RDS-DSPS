#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JEDNORÁZOVĚ nahraje rds_data.json do Firebase Realtime Database
(struktura stavby/<id> + objekty/<id>/<oN>). Po nasazení už NESPOUŠTĚJ –
hlavní zdroj dat je pak Firebase (edituješ v appce), opětovné spuštění
by přepsalo ruční úpravy.

Přihlašovací údaje bere z firebase.local.json (necommituje se).
"""
import json, os, sys, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL = os.path.join(HERE, "firebase.local.json")
DATA  = os.path.join(HERE, "rds_data.json")

def signin(cfg):
    url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=" + cfg["apiKey"]
    body = json.dumps({"email": cfg["email"], "password": cfg["password"], "returnSecureToken": True}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())["idToken"]

def put(dburl, path, token, obj):
    url = dburl.rstrip("/") + "/" + path + ".json?auth=" + token
    req = urllib.request.Request(url, data=json.dumps(obj, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json"}, method="PUT")
    return urllib.request.urlopen(req).getcode()

def main():
    if not os.path.exists(LOCAL):
        print("Chybí firebase.local.json (vzor: firebase.local.json.example)."); sys.exit(1)
    cfg = json.load(open(LOCAL))
    data = json.load(open(DATA))
    if input("Nahrát rds_data.json do Firebase? Přepíše /stavby a /objekty. Napiš ANO: ").strip() != "ANO":
        print("Zrušeno."); return
    token = signin(cfg)
    stavby, objekty = {}, {}
    for sid, s in data.get("stavby", {}).items():
        stavby[sid] = {"nazev": s["nazev"], "typ": s.get("typ", "RDS"), "poradi": 1}
        objekty[sid] = {}
        for i, o in enumerate(s.get("objekty", [])):
            objekty[sid]["o%03d" % i] = o
    print("stavby:", put(cfg["dbUrl"], "stavby", token, stavby))
    print("objekty:", put(cfg["dbUrl"], "objekty", token, objekty))
    print("Hotovo. Zkontroluj appku.")

if __name__ == "__main__":
    main()
