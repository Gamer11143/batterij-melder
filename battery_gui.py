import json
import os
import sys
import time
from plyer import notification
import psutil
import tkinter as tk
import tkinter.messagebox as messagebox
import webview
import subprocess
import threading
import urllib.request
import urllib.parse
from scapy.all import sniff, IP


toegestane_ips_lijst = {
    "145.93.164.15",  #netwerk van school
    "145.93.164.64",  #netwerk van school
    "77.161.37.113"      #netwerk thuis
}

geblokkeerd_ips = set()

# Instellingen voor de batterij
BATTERIJ_VOL = 95
BATTERIJ_BIJNA_VOL = 80
BATTERIJ_LEEG = 20

# Welke meldingen zijn er al gestuurd?
vol_gemeld = False
bijna_vol_gemeld = False
leeg_gemeld = False

# Bestand waar toestemming in staat
CONFIG_BESTAND = "config.json"

def vraag_toestemming_pop_up():

    uitslag = {"toestemming": False}
    # Maak een pop-up venster om toestemming te vragen
    root = tk.Tk()
    venster = root
    venster.title("Toestemming voor meldingen ontvangen")
    venster.geometry("400x200")
    venster.resizable(False, False)
    # tekst boven in de pop up venster
    label=tk.Label(venster, text="Wilt u meldingen ontvangen over de batterijstatus?", font=("Arial", 12))
    label.pack(pady=20)

    #functie om de toestemming op te slaan in config.json
    def keuze(gekozen_optie):
        uitslag["toestemming"] = (gekozen_optie == "ja")
        venster.destroy()

    #knoppen
    knop1 = tk.Button(venster, text="Ja", width=10, bg="#32CD32", command=lambda: keuze("ja"))
    knop1.pack(side=tk.LEFT, padx=50)

    knop2 = tk.Button(venster, text="Nee", width=10, bg="#FF0000", command=lambda: keuze("nee"))
    knop2.pack(side=tk.LEFT, padx=50)

    #toon venster en wacht tot de gebruiker een antwoord heeft gegeven
    venster.mainloop()

    #sla de uitslag op in het bestand
    with open(CONFIG_BESTAND, "w") as f:
        json.dump({"permission": uitslag["toestemming"]} , f)

    return uitslag["toestemming"]

def check_toestemming():
    # Kijken of het config bestand bestaat
    if os.path.exists(CONFIG_BESTAND):
        try:
            with open(CONFIG_BESTAND, "r") as f:
                data = json.load(f)
                return data.get("permission", False)
        except Exception:
            return False
    return False


def stuur_melding(titel, bericht, seconden):
    try:
        notification.notify(
            title=titel,
            message=bericht,
            app_name="Laptop Battery Monitor",
            timeout=seconden,
        )
    except Exception as e:
        print(f"[!] Fout bij het sturen van melding: {e}")

    try:
        #via ntfy krijg je de meldingen over de batterij. Dat kan via telefoon en laptop.
        ntfy_url = "https://ntfy.sh/Laptop0162"

        schone_titel = titel.encode('ascii', 'ignore').decode('ascii').strip()
        schoon_bericht = bericht.encode('ascii', 'ignore').decode('ascii').strip()

        if not schone_titel:
            schone_titel = "batterij status"

        req = urllib.request.Request(
            ntfy_url,
            data=schoon_bericht.encode("utf-8"),
            headers={
                "Title": schone_titel,
                "Priority": "high",
            },
            method="POST"
        )
        urllib.request.urlopen(req, timeout =10)
        print(f"[+] ntfy verzonden naar telefoon")

    except Exception as e:
        print(f"[!] Fout bij het verzenden van ntfy melding: {e}")

class Api:
    def login(self, gebruikersnaam, wachtwoord):
        if geblokkeerd_ips:
            stuur_melding(
                "Toegang geweigerd",
                "Inloggen niet toegstaan vanaf dit netwerk/IP-adres.",
                5
            )
            return False
        
        # Hier kun je de inloggegevens controleren
        if gebruikersnaam == "admin" and wachtwoord == "wachtwoord":
            stuur_melding(
                "Inloggen gelukt",
                f"Welkom terug, {gebruikersnaam}",
                5
            )
            return True

        else:
            stuur_melding(
                "Inloggen mislukt",
                f"Inloggen mislukt voor gebruiker {gebruikersnaam}",
                5
            )
            return False

    def get_batterij_status(self):
        batterij = psutil.sensors_battery()
        if batterij:
            return {
                "percentage": batterij.percent,
                "status": "Op netstroom" if batterij.power_plugged else "Op batterij",
                "charging": "Opladen" if batterij.power_plugged else "Batterij"
            }
        return {"percentage": 0, "status": "geen batterij", "charging": "Onbekend" }

    def set_thresholds(self, vol, bijna_vol, leeg):
        global BATTERIJ_VOL, BATTERIJ_BIJNA_VOL, BATTERIJ_LEEG
        BATTERIJ_VOL = vol
        BATTERIJ_BIJNA_VOL = bijna_vol
        BATTERIJ_LEEG = leeg

    def get_notification_setting(self):
        return check_toestemming()

    def set_notifications(self, actief):
        with open(CONFIG_BESTAND, "w") as f:
            json.dump({"permission": actief}, f)

# Start van het hoofdprogramma
print("Batterij monitor wordt gestart...")

#Vraag altijd om toestemming bij opstarten
toestemming = vraag_toestemming_pop_up()
print(f"Gekozen instelling: {toestemming}")

if not toestemming:
    print("Meldingen zijn uitgeschakeld. U kunt de website niet gebruiken.")
    sys.exit()

if getattr(sys, 'frozen', False):
    script_map = os.path.dirname(sys.executable)
else:
    script_map = os.path.dirname(os.path.abspath(__file__))

html_pad = os.path.join(script_map, "..", "index.html")

with open (html_pad, "r", encoding="utf-8") as f:
    html_inhoud = f.read()

html_abs_pad = os.path.abspath(html_pad)

api = Api()
window = webview.create_window(
    "Laptop Batterij Monitor",
    url=html_abs_pad,
    js_api=api,
    background_color='#FFFFFF'
)

# De achtergrondfunctie voor de meldingen
def achtergrond_check():
    def controleer_batterij():
        global vol_gemeld, bijna_vol_gemeld, leeg_gemeld

        while True:
            time.sleep(10)

            if not check_toestemming():
                continue

            batterij = psutil.sensors_battery()
            if not batterij:
                continue

            percentage = batterij.percent
            aan_lader = batterij.power_plugged

            if percentage >= BATTERIJ_VOL and aan_lader:
                if not vol_gemeld:
                    stuur_melding(
                        "Batterijstatus: Vol",
                        f"De batterij is volledig opgeladen ({percentage}%). U kunt de oplader loskoppelen.",
                        10
                    )
                    vol_gemeld = True
            elif not aan_lader:
                vol_gemeld = False

            if percentage >= BATTERIJ_BIJNA_VOL and percentage < BATTERIJ_VOL and aan_lader:
                if not bijna_vol_gemeld:
                    stuur_melding(
                        "Batterijstatus: Bijna Vol",
                        f"De batterij is bijna volledig opgeladen ({percentage}%). U kunt de oplader loskoppelen.",
                        10
                    )
                    bijna_vol_gemeld = True
            elif not aan_lader:
                bijna_vol_gemeld = False

            elif percentage <= BATTERIJ_LEEG and not aan_lader:
                if not leeg_gemeld:
                    stuur_melding(
                        "Batterijstatus: Bijna leeg",
                        f"De batterij is bijna leeg ({percentage}%). Sluit de oplader aan om te voorkomen dat de laptop uitvalt.",
                        10
                    )
                    leeg_gemeld = True
            elif not aan_lader:
                leeg_gemeld = False


    threading.Thread(target=controleer_batterij, daemon=True).start()
    return

def verwerk_pakket(pakket):
    toestemming_actueel = check_toestemming()

    if pakket.haslayer(IP) and toestemming_actueel:
        src_ip = pakket[IP].src

        is_lokaal = (
            src_ip.startswith("192.168.") or
            src_ip.startswith("10.") or
            src_ip.startswith("172.") or
            src_ip.startswith("127.")
        )

        is_bekend_webverkeer = (
            src_ip.startswith("8.8.") or
            src_ip.startswith("1.1.1.") or
            src_ip.startswith("9.9.") or
            src_ip.startswith("208.67.")
        )

        # Als de ip niet lokaal, whitelist en geblokkeerd is:
        if not is_lokaal and not is_bekend_webverkeer and src_ip not in toegestane_ips_lijst and src_ip not in geblokkeerd_ips:
            print(f"[!] Onbekend IP-adres gedetecteerd: {src_ip}")
            geblokkeerd_ips.add(src_ip)

            os._exit(1)

def start_sniffer():
    print("[*] Start met het monitoren van netwerkverkeer via scapy")
    sniff(filter="ip", prn=verwerk_pakket, store=0, IFACES=None)

threading.Thread(target=start_sniffer, daemon=True).start()
    
webview.start(func=achtergrond_check, debug=False)
threading.Thread(target=start_sniffer, daemon=True).start()
    
webview.start(func=achtergrond_check, debug=False)
