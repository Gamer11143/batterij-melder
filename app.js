// --- BASIS VARIABELEN ---
var GAUGE_LENGTE = 518.36; // Lengte van de boog uit HTML

// --- SCRIPT START ---
console.log("App is gestart!");

// Luister naar de sliders wanneer er iets verandert
document.getElementById("warningSlider").addEventListener("input", verwerkInstellingen);
document.getElementById("limitSlider").addEventListener("input", verwerkInstellingen);
document.getElementById("lowSlider").addEventListener("input", verwerkInstellingen);

function verwerkInstellingen() {
    // 1. Haal de gekozen waarden op uit de HTML sliders
    var waarschuwing = Number(document.getElementById("warningSlider").value);
    var limiet = Number(document.getElementById("limitSlider").value);
    var laag = Number(document.getElementById("lowSlider").value);

    // 2. Pas de teksten aan naast de sliders
    document.getElementById("warningValue").textContent = waarschuwing + "%";
    document.getElementById("limitValue").textContent = limiet + "%";
    document.getElementById("lowValue").textContent = laag + "%";

    var hintTekst = document.getElementById("settingsHint");
    var opslaanKnop = document.getElementById("saveButton");

    // 3. Controleer of de waarschuwing niet hoger is dan de limiet
    if (waarschuwing >= limiet) {
        hintTekst.textContent = "❌ De 'Meldingdrempel' moet lager zijn dan de 'Laadlimiet'.";
        hintTekst.className = "hint";
        if (opslaanKnop) opslaanKnop.style.opacity = 0.5;
    } else {
        hintTekst.textContent = "✅ wijzigingen zijn opgeslagen";
        hintTekst.className = "hint ok";
        if (opslaanKnop) opslaanKnop.style.opacity = 1;

        // Stuur de nieuwe instellingen direct door naar Python
        if (window.pywebview && pywebview.api) {
            pywebview.api.set_thresholds(limiet, waarschuwing, laag);
            if (opslaanKnop) opslaanKnop.textContent = "✓ Automatisch"; 
        }
    }
    leegMeldingGestuurd = false;
    volMeldingGestuurd = false;
    haalBatterijOp();
}

function updateMeter(percentage) {
    // Zorg dat het percentage netjes tussen 0 en 100 blijft
    if (percentage < 0) percentage = 0;
    if (percentage > 100) percentage = 100;

    // Pas het percentage op het scherm aan
    document.getElementById("percentage").textContent = Math.round(percentage) + "%";

    // Bereken de lengte van de gekleurde streep
    var berekening = GAUGE_LENGTE * (1 - percentage / 100);
    document.getElementById("gauge-progress").style.strokeDashoffset = berekening;
}

function vraagBrowserToestemming() {
    if("Notification" in window) {
        Notification.requestPermission().then(function(permission) {
            var checkbox = document.getElementById("notificationsCheckbox");
            if (checkbox) checkbox.checked = (permission === 'granted');
        });
    }
}

var leegMeldingGestuurd = false;
var volMeldingGestuurd = false;

var toegestaneIPs =["145.93.164.15", "77.161.37.113"];

function controleerIPEnStart() {
    if (window.pywebview && pywebview.api) {
        haalBatterijOp();
        return;
    }

    fetch('https://api.ipify.org?format=json')
        .then(function(response) { return response.json(); })
        .then(function(data) {
            var bezoekerIP = data.ip;
            console.log("Jouw IP-adres is", bezoekerIP);

            var isSchoolNetwerk = bezoekerIP.startsWith("145.93.164.15")
            var isThuisNetwerk = toegestaneIPs.includes(bezoekerIP);

            //Als de IP Adres niet op de whitelist staat, blokkeer dan de toegang van de website van de gebruiker.
            if (!isSchoolNetwerk && !isThuisNetwerk) {
                document.body.innerHTML = "<h1 style='color:red; text-align:center; margin-top:50px; '>403 - Toegang Geweigerd</h1><p style='text-align; center;'>Uw IP-adres (" + bezoekerIP + ") heeft geen toegang tot deze applicatie. </p>";
            } else {
                // IP Adres wel toegestaan
                haalBatterijOp    
            }
        })
        .catch(function(err) {
            console.error("Kon IP niet controleren:", err);
            document.body.innerHTML = "<div style= 'text-align: center; padding-top:100px;' ><h1 style:red; front-size:40px; '>Fout bij IP-controle'</h1></div>";
        });
}

function haalBatterijOp() {
    // A. Als het in python draait
    if (window.pywebview && pywebview.api) {
        pywebview.api.get_batterij_status().then(function(status) {
            updateMeter(status.percentage);
            document.getElementById("batteryStatus").textContent = status.status;
            document.getElementById("plugged").textContent = status.charging;

            // Verbinding-bolletje groen maken
            var verbindingBox = document.getElementById("connection");
            if (verbindingBox) {
                verbindingBox.innerHTML = '<span class="dot" style="background: #22c55e;"></span> <span>Verbonden </span>';
            }
        });
    }

    // B. Als het in Chrome/Safari opent. 
    else if (navigator.getBattery) {
        navigator.getBattery().then(function(battery) {
            var percentage = Math.round(battery.level * 100);
            var statustekst = battery.charging ? "Op netstroom" : "Op batterij";
            var chargingTekst = battery.charging ? "Opladen" : "Batterij";
            
            updateMeter(percentage);
            document.getElementById("batteryStatus").textContent = statustekst;
            document.getElementById("plugged").textContent = chargingTekst;
            var verbindingBox = document.getElementById("connection");
            if (verbindingBox) {
            verbindingBox.innerHTML = '<span class="dot" style="background: #22c55e;"></span> <span></span>';
            }     
            
            if (Notification.permission === "granted" && document.getElementById("notificationsCheckbox").checked) {
            var laagDrempel = Number(document.getElementById("lowSlider").value);
            var waarschuwingDrempel = Number(document.getElementById("warningSlider").value);
            var limietDrempel = Number(document.getElementById("limitSlider").value);

            //1. Batterij bijna leeg
            if (!battery.charging && percentage <= laagDrempel) {
                if (!leegMeldingGestuurd) {
                    new Notification ("Batterij bijna leeg", {
                        body: "Je batterij is nog maar " + percentage + "%, Sluit je laptop aan de oplader."
                    });
                    leegMeldingGestuurd = true;
                }
            } else if (percentage > laagDrempel) {
                leegMeldingGestuurd = false;
            }
            //2. Batterij bijna vol of vol
            if (battery.charging && (percentage >= waarschuwingDrempel || percentage>= limietDrempel)) {
                if (!volMeldingGestuurd) {
                    new Notification ("Batterij opgeladen", {
                        body: "Je batterij is al " + percentage + "%, Je kan je laptop loskoppelen van de oplader."
                    });
                    volMeldingGestuurd = true;
                }
            } else if (!battery.charging) {
                volMeldingGestuurd = false;
            }
        }
    });
}        
    else {
        //Als de browser geen battery API ondersteunt
        var verbindingBox = document.getElementById("connection");
        if (verbindingBox) {
            verbindingBox.innerHTML = '<span class="dot" style="background: #ef4444;"></span> <span>Geen verbinding</span>';  
        }
    }
}   

// Haal direct de status op en de toestemming bij het laden van de pagina
document.addEventListener("DOMContentLoaded", function() {
    vraagBrowserToestemming();
    controleerIPEnStart();
});

window.addEventListener("pywebviewready", function() {
    haalBatterijOp();

    if (window.pywebview && pywebview.api && pywebview.api.get_notification_setting) {
        pywebview.api.get_notification_setting().then(function(actief) {
            document.getElementById("notificationsCheckbox").checked = actief;
        });
    }
});

// Luister naar veranderingen in het vinkje bij de instellingen
document.getElementById("notificationsCheckbox").addEventListener("change", function(e) {
    var isChecked = e.target.checked;

    // Stuur de nieuwe keuze direct door naar Python om op te slaan
    if (window.pywebview && pywebview.api && pywebview.api.set_notifications) {
        pywebview.api.set_notifications(isChecked);
    }    
});

// Update alle cijfers meteen op het scherm
//verwerkInstellingen();

// Check elke 5 seconden de batterij
setInterval(function() {
    controleerIPEnStart();
}, 5000);