//oberflaeche der bruecke: projekte, graph, dienste, anordnung
var knoten = [];
var kanten = [];
var label_felder = {};
var yaw = 0.35;
var pitch = 0.12;
var yaw_tempo = 0.0008;
var pitch_tempo = 0;
var abstand = 4.8;
var BLICK = 300;
var zieht = false;
var schiebt = false;
var schiebe_id = "";
var letzter_x = 0;
var letzter_y = 0;
var start_x = 0;
var start_y = 0;
var hat_gezogen = false;
var gewaehlt = "";
var laufzeit = 0;
var tab_aktiv = (function () {
  var wert = "";
  try {
    wert = new URLSearchParams(window.location.search).get("tab") || "";
  } catch (fehler) {
    wert = "";
  }
  if (wert === "projekte" || wert === "dienste" || wert === "alle") {
    return wert;
  }
  return "projekte";
})();
var lage_agenten = [];
var lage_text = "";
var karten_sig = "";
var graph_sig = "";
var protokoll_sig = "";
var log_sig = "";
var bericht_sig = "";
var bericht_stand_text = "";
var bericht_naechstes_text = "";
var protokoll_fuer = "";
var log_fuer = "";
var bericht_fuer = "";
var vorschlag_haken = {};
var wege_fuer = "";
var wege_liste = [];
var hinweis_timer = null;
var anordnung = {eintraege: []};
var anordnung_geladen = false;
var zentrale_stand = {projekte: []};
var ziehe_von_griff = false;
var speicher_timer = null;
var dienst_offen_id = "";
var start_projekt = (function () {
  var wert = "";
  try {
    wert = new URLSearchParams(window.location.search).get("projekt") || "";
  } catch (fehler) {
    wert = "";
  }
  return wert;
})();

var KUGEL_FARBEN = [
  ["#5eead4", "#0f766e"],
  ["#c4b5fd", "#6d28d9"],
  ["#93c5fd", "#1d4ed8"]
];

var FESTE_FARBEN = {
  profil: ["#e9d5ff", "#6d28d9"]
};

function kuerze(text, grenze) {
  if (!text) {
    return "";
  }
  if (text.length <= grenze) {
    return text;
  }
  return text.slice(0, grenze - 1) + "…";
}

function zentrale_map() {
  var map = {};
  var liste = (zentrale_stand && zentrale_stand.projekte) || [];
  var i;
  var p;
  for (i = 0; i < liste.length; i++) {
    p = liste[i];
    if (p && p.id) {
      map[p.id] = p;
    }
  }
  return map;
}

function alle_projekte() {
  var dev = (window.dev_status && window.dev_status.projekte) || {};
  var z = zentrale_map();
  var name;
  var r = {};
  for (name in dev) {
    if (Object.prototype.hasOwnProperty.call(dev, name)) {
      r[name] = dev[name];
    }
  }
  for (name in z) {
    if (!Object.prototype.hasOwnProperty.call(z, name)) {
      continue;
    }
    r[name] = Object.assign({}, r[name] || {}, {
      name: z[name].name || name,
      pfad: z[name].pfad || (r[name] && r[name].pfad) || "",
      zustand: z[name].zustand || (r[name] && r[name].zustand) || "leer",
      letzter_auftrag: z[name].letzter_auftrag || (r[name] && r[name].letzter_auftrag) || "",
      stand_text: (z[name].stand_jetzt && z[name].stand_jetzt.text) || "",
      ende: (z[name].stand_jetzt && z[name].stand_jetzt.zuletzt) || (r[name] && r[name].ende) || "",
      zentrale: z[name]
    });
  }
  return r;
}

function sende_loop_start(projekt, autonom) {
  var body = {projekt: projekt};
  if (autonom) {
    body.modus = "autonom";
    body.ja = true;
  } else {
    body.modus = "schrittweise";
  }
  return fetch("/zentrale/loop/start", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  }).then(function (antwort) {
    return antwort.json().then(function (daten) {
      return {ok: antwort.ok, body: daten};
    });
  });
}

function loop_satz(eintrag) {
  var st = eintrag && eintrag.zentrale && eintrag.zentrale.loop_status;
  var teile = [];
  if (!st) {
    return "";
  }
  if (st.phase) {
    teile.push("loop " + st.phase);
  }
  if (st.aktuell) {
    teile.push("jetzt " + st.aktuell);
  }
  if (st.offen && st.offen.length) {
    teile.push("offen " + st.offen.join(", "));
  }
  if (st.fragen && st.fragen.length) {
    teile.push("fragen " + st.fragen.length);
  }
  if (st.letzter_fehler) {
    teile.push("fehler");
  }
  return teile.join(" · ");
}

function sende_freigabe(projekt, aktion, ja) {
  var body = {projekt: projekt, aktion: aktion};
  if (ja) {
    body.ja = true;
  }
  if (aktion === "ablehnen") {
    body.ablehnen = true;
  }
  return fetch("/zentrale/git/freigabe", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  }).then(function (antwort) {
    return antwort.json().then(function (daten) {
      return {ok: antwort.ok, body: daten};
    });
  });
}

function zeichne_nach_stand() {
  var projekte = alle_projekte();
  var sig = Object.keys(projekte).sort().join("|");
  sync_knoten_stand(projekte);
  zeichne_zaehler(projekte);
  if (sig !== graph_sig) {
    graph_sig = sig;
    baue_graph(projekte);
    baue_labels();
    if (start_projekt && projekte[start_projekt]) {
      waehle(start_projekt);
      start_projekt = "";
    } else if (!gewaehlt || (!finde_knoten(gewaehlt) && gewaehlt !== "profil")) {
      if (finde_knoten("profil")) {
        waehle("profil");
      }
    }
  } else if (start_projekt && projekte[start_projekt]) {
    waehle(start_projekt);
    start_projekt = "";
  } else if (gewaehlt && gewaehlt !== "profil") {
    zeichne_panel(projekte[gewaehlt]);
  }
  karten_sig = "";
  zeichne_karten();
}

function hole_zentrale() {
  return fetch("/zentrale/projekte")
    .then(function (antwort) {
      if (!antwort.ok) {
        throw new Error("zentrale");
      }
      return antwort.json();
    })
    .then(function (daten) {
      zentrale_stand = daten || {projekte: []};
      window.zentrale = zentrale_stand;
      zeichne_nach_stand();
    })
    .catch(function () {
      return null;
    });
}

function knoten_ids() {
  var ids = [];
  var i;
  var name;
  var projekte;
  for (i = 0; i < knoten.length; i++) {
    if (knoten[i].id && knoten[i].id !== "profil") {
      ids.push(knoten[i].id);
    }
  }
  if (ids.length) {
    return ids;
  }
  projekte = alle_projekte();
  for (name in projekte) {
    if (Object.prototype.hasOwnProperty.call(projekte, name)) {
      ids.push(name);
    }
  }
  return ids;
}

function gleicher_stamm(a, b) {
  if (!a || !b) {
    return false;
  }
  if (a === b) {
    return true;
  }
  if (a.indexOf(b + "-") === 0 || b.indexOf(a + "-") === 0) {
    return true;
  }
  return false;
}

function ziel_fuer_projekt(projekt) {
  var p = String(projekt || "").toLowerCase();
  var ids = knoten_ids();
  var i;
  for (i = 0; i < ids.length; i++) {
    if (gleicher_stamm(String(ids[i]).toLowerCase(), p)) {
      return ids[i];
    }
  }
  return "";
}

function agenten_am_knoten(knoten_id) {
  var liste = [];
  var i;
  var agent;
  if (!knoten_id || knoten_id === "profil") {
    return liste;
  }
  for (i = 0; i < lage_agenten.length; i++) {
    agent = lage_agenten[i];
    if (ziel_fuer_projekt(agent.projekt) === knoten_id) {
      liste.push(agent);
    }
  }
  return liste;
}

function laufende_agenten(knoten_id) {
  var alle = agenten_am_knoten(knoten_id);
  var liste = [];
  var i;
  for (i = 0; i < alle.length; i++) {
    if (alle[i].stand === "laeuft") {
      liste.push(alle[i]);
    }
  }
  return liste;
}

function letzte_agenten(knoten_id) {
  var alle = agenten_am_knoten(knoten_id);
  var lauf = [];
  var problem = [];
  var i;
  for (i = 0; i < alle.length; i++) {
    if (alle[i].stand === "laeuft") {
      lauf.push(alle[i]);
    } else if (alle[i].stand === "problem") {
      problem.push(alle[i]);
    }
  }
  if (lauf.length) {
    return lauf;
  }
  if (problem.length) {
    return problem;
  }
  if (alle.length) {
    return [alle[0]];
  }
  return [];
}

function text_der_arbeit(agenten, kn) {
  var teile = [];
  var i;
  var agent;
  var n;
  if (agenten && agenten.length) {
    n = Math.min(agenten.length, 2);
    for (i = 0; i < n; i++) {
      agent = agenten[i];
      teile.push((agent.name || agent.id || "agent") + " · " + (agent.stand || "laeuft") + " · " + kuerze(agent.tun || "arbeitet", 56));
    }
    if (agenten.length > 2) {
      teile.push("+" + (agenten.length - 2));
    }
    return teile.join("\n");
  }
  if (kn && kn.zustand === "laeuft") {
    return "laeuft · " + kuerze(kn.letzter_auftrag || "arbeitet", 70);
  }
  return "";
}

function sync_knoten_stand(projekte) {
  var i;
  var eintrag;
  for (i = 0; i < knoten.length; i++) {
    eintrag = projekte[knoten[i].id];
    if (!eintrag) {
      continue;
    }
    knoten[i].zustand = eintrag.zustand || "leer";
    knoten[i].letzter_auftrag = eintrag.letzter_auftrag || "";
  }
}

function setze_hinweis(text) {
  var feld = document.querySelector("#hover_info");
  if (!feld) {
    return;
  }
  feld.textContent = text;
  if (hinweis_timer) {
    clearTimeout(hinweis_timer);
  }
  hinweis_timer = setTimeout(function () {
    feld.textContent = hover_standard();
  }, 4000);
}

function hover_standard() {
  if (tab_aktiv === "dienste") {
    return "hover zeigt ort";
  }
  if (tab_aktiv === "alle") {
    return "hover zeigt pfad/ort · ziehen sortiert";
  }
  return "hover zeigt pfad";
}

function farbe_fuer(id) {
  var summe = 0;
  var i;
  if (FESTE_FARBEN[id]) {
    return FESTE_FARBEN[id];
  }
  for (i = 0; i < id.length; i++) {
    summe += id.charCodeAt(i);
  }
  return KUGEL_FARBEN[summe % KUGEL_FARBEN.length];
}

function ort_fuer(name, index, gesamt) {
  var winkel;
  var radius;
  if (name === "profil") {
    return {x: 0, y: 0.05, z: 0, r: 0.56};
  }
  winkel = (index / Math.max(gesamt, 1)) * Math.PI * 2 - Math.PI / 2;
  radius = 2.05 + (index % 3) * 0.12;
  return {
    x: Math.cos(winkel) * radius,
    y: Math.sin(winkel) * 1.35,
    z: Math.sin(winkel * 1.3) * 0.55,
    r: 0.34
  };
}

function finde_knoten(id) {
  var i;
  for (i = 0; i < knoten.length; i++) {
    if (knoten[i].id === id) {
      return knoten[i];
    }
  }
  return null;
}

function haengt_an(id) {
  var liste = [];
  var i;
  for (i = 0; i < knoten.length; i++) {
    if (knoten[i].eltern === id) {
      liste.push(knoten[i].id);
      liste = liste.concat(haengt_an(knoten[i].id));
    }
  }
  return liste;
}

function baue_graph(projekte) {
  var alt = {};
  var i;
  var name;
  var ort;
  var namen = Object.keys(projekte || {}).sort();
  for (i = 0; i < knoten.length; i++) {
    alt[knoten[i].id] = {x: knoten[i].x, y: knoten[i].y, z: knoten[i].z};
  }
  knoten = [];
  kanten = [];
  ort = ort_fuer("profil", 0, 1);
  knoten.push({
    id: "profil",
    name: "profil",
    x: ort.x,
    y: ort.y,
    z: ort.z,
    r: ort.r,
    eltern: "",
    sichtbar: true,
    sx: 0,
    sy: 0,
    sr: 0,
    zustand: ""
  });
  for (i = 0; i < namen.length; i++) {
    name = namen[i];
    ort = ort_fuer(name, i, namen.length);
    knoten.push({
      id: name,
      name: name,
      x: ort.x,
      y: ort.y,
      z: ort.z,
      r: ort.r,
      eltern: "profil",
      sichtbar: true,
      sx: 0,
      sy: 0,
      sr: 0,
      zustand: (projekte[name] && projekte[name].zustand) || "leer",
      letzter_auftrag: (projekte[name] && projekte[name].letzter_auftrag) || ""
    });
    kanten.push({von: "profil", nach: name});
  }
  for (i = 0; i < knoten.length; i++) {
    if (alt[knoten[i].id]) {
      knoten[i].x = alt[knoten[i].id].x;
      knoten[i].y = alt[knoten[i].id].y;
      knoten[i].z = alt[knoten[i].id].z;
    }
  }
}

function baue_labels() {
  var box = document.querySelector("#labels");
  var i;
  var feld;
  var name_el;
  var live_el;
  box.textContent = "";
  label_felder = {};
  for (i = 0; i < knoten.length; i++) {
    feld = document.createElement("button");
    feld.type = "button";
    feld.className = "label";
    name_el = document.createElement("span");
    name_el.className = "label_name";
    name_el.textContent = knoten[i].name;
    live_el = document.createElement("span");
    live_el.className = "label_live";
    feld.appendChild(name_el);
    feld.appendChild(live_el);
    feld.setAttribute("data-id", knoten[i].id);
    feld.addEventListener("pointerdown", function (ereignis) {
      ereignis.preventDefault();
      ereignis.stopPropagation();
      starte_schieben(ereignis.currentTarget.getAttribute("data-id"), ereignis.clientX, ereignis.clientY);
    });
    box.appendChild(feld);
    label_felder[knoten[i].id] = feld;
  }
}

function drehe(x, y, z) {
  var cos_y = Math.cos(yaw);
  var sin_y = Math.sin(yaw);
  var x1 = x * cos_y + z * sin_y;
  var z1 = -x * sin_y + z * cos_y;
  var cos_p = Math.cos(pitch);
  var sin_p = Math.sin(pitch);
  return {
    x: x1,
    y: y * cos_p - z1 * sin_p,
    z: y * sin_p + z1 * cos_p
  };
}

function buehnen_mass() {
  var box = document.querySelector("#mitte");
  return {breite: box.clientWidth, hoehe: box.clientHeight};
}

function projiziere(punkt, breite, hoehe) {
  var gedreht = drehe(punkt.x, punkt.y, punkt.z);
  var tiefe = gedreht.z + abstand;
  var skala = 1.7 / tiefe;
  return {
    sx: breite * 0.5 + gedreht.x * skala * BLICK,
    sy: hoehe * 0.46 - gedreht.y * skala * BLICK,
    skala: skala,
    tiefe: tiefe
  };
}

function schiebe_welt(id, dx_px, dy_px) {
  var ziel = finde_knoten(id);
  var gedreht;
  var skala;
  var rx;
  var ry;
  var cos_p;
  var sin_p;
  var cos_y;
  var sin_y;
  var y;
  var z1;
  var gruppe;
  var i;
  var kn;
  if (!ziel) {
    return;
  }
  gedreht = drehe(ziel.x, ziel.y, ziel.z);
  skala = 1.7 / (gedreht.z + abstand);
  rx = dx_px / (skala * BLICK);
  ry = -dy_px / (skala * BLICK);
  cos_p = Math.cos(pitch);
  sin_p = Math.sin(pitch);
  y = ry * cos_p;
  z1 = -ry * sin_p;
  cos_y = Math.cos(yaw);
  sin_y = Math.sin(yaw);
  gruppe = [id].concat(haengt_an(id));
  for (i = 0; i < gruppe.length; i++) {
    kn = finde_knoten(gruppe[i]);
    kn.x += rx * cos_y - z1 * sin_y;
    kn.y += y;
    kn.z += rx * sin_y + z1 * cos_y;
  }
}

function zeichne_bogen(ctx, x1, y1, x2, y2, hell) {
  var mx = (x1 + x2) / 2;
  var my = (y1 + y2) / 2;
  var dx = x2 - x1;
  var dy = y2 - y1;
  var laenge = Math.sqrt(dx * dx + dy * dy) || 1;
  var cx = mx - (dy / laenge) * 28;
  var cy = my + (dx / laenge) * 28;
  ctx.strokeStyle = "rgba(160, 190, 255, " + hell + ")";
  ctx.lineWidth = 1.1;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.quadraticCurveTo(cx, cy, x2, y2);
  ctx.stroke();
}

function zeichne_kugel(ctx, x, y, radius, hell, aktiv, farben, arbeitet) {
  var puls = (aktiv || arbeitet) ? 1 + Math.sin(laufzeit * 2.2) * 0.05 : 1;
  var r = radius * puls;
  var koerper;
  ctx.save();
  ctx.globalAlpha = hell;
  koerper = ctx.createRadialGradient(x - r * 0.32, y - r * 0.38, r * 0.08, x, y, r);
  koerper.addColorStop(0, "#f8fbff");
  koerper.addColorStop(0.4, farben[0]);
  koerper.addColorStop(1, farben[1]);
  ctx.fillStyle = koerper;
  ctx.shadowColor = farben[0];
  ctx.shadowBlur = (aktiv || arbeitet) ? 30 : 16;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;
  if (arbeitet) {
    ctx.strokeStyle = "rgba(94, 234, 212, 0.95)";
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.arc(x, y, r + 16 + Math.sin(laufzeit * 3.1) * 3.5, 0, Math.PI * 2);
    ctx.stroke();
  }
  if (aktiv) {
    ctx.strokeStyle = "rgba(255,255,255,0.8)";
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.arc(x, y, r + 9 + Math.sin(laufzeit * 2.2) * 2.5, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
}

function zeichne_szene() {
  var leinwand = document.querySelector("#buehne");
  var ctx = leinwand.getContext("2d");
  var mass = buehnen_mass();
  var breite = mass.breite;
  var hoehe = mass.hoehe;
  var bilder = [];
  var i;
  var a;
  var von;
  var nach;
  var hell;
  var aktiv;
  var arbeitet;
  var radius;
  var feld;
  var agenten_hier;
  var live_text;
  var live_feld;
  ctx.clearRect(0, 0, breite, hoehe);
  for (i = 0; i < knoten.length; i++) {
    if (!knoten[i].sichtbar) {
      continue;
    }
    bilder.push({knoten: knoten[i], bild: projiziere(knoten[i], breite, hoehe)});
  }
  for (i = 0; i < kanten.length; i++) {
    von = null;
    nach = null;
    for (a = 0; a < bilder.length; a++) {
      if (bilder[a].knoten.id === kanten[i].von) {
        von = bilder[a];
      }
      if (bilder[a].knoten.id === kanten[i].nach) {
        nach = bilder[a];
      }
    }
    if (!von || !nach) {
      continue;
    }
    hell = !gewaehlt || kanten[i].von === gewaehlt || kanten[i].nach === gewaehlt ? 0.85 : 0.32;
    zeichne_bogen(ctx, von.bild.sx, von.bild.sy, nach.bild.sx, nach.bild.sy, hell);
  }
  bilder.sort(function (links, rechts) {
    return rechts.bild.tiefe - links.bild.tiefe;
  });
  for (i = 0; i < bilder.length; i++) {
    aktiv = bilder[i].knoten.id === gewaehlt;
    agenten_hier = letzte_agenten(bilder[i].knoten.id);
    arbeitet = laufende_agenten(bilder[i].knoten.id).length > 0 || bilder[i].knoten.zustand === "laeuft";
    hell = !gewaehlt || aktiv || arbeitet || bilder[i].knoten.id === "profil" ? 1 : 0.78;
    radius = Math.max(8, bilder[i].knoten.r * bilder[i].bild.skala * BLICK * (aktiv || arbeitet ? 1.18 : 1));
    zeichne_kugel(ctx, bilder[i].bild.sx, bilder[i].bild.sy, radius, hell, aktiv, farbe_fuer(bilder[i].knoten.id), arbeitet);
    feld = label_felder[bilder[i].knoten.id];
    if (feld) {
      feld.style.display = "block";
      feld.style.left = bilder[i].bild.sx + "px";
      if (bilder[i].bild.sy - radius < 28) {
        feld.style.top = (bilder[i].bild.sy + radius + 16) + "px";
      } else {
        feld.style.top = (bilder[i].bild.sy - radius - 16) + "px";
      }
      feld.style.transform = "translate(-50%, -50%)";
      feld.classList.toggle("aktiv", aktiv);
      feld.classList.toggle("arbeitet", arbeitet);
      feld.classList.toggle("erledigt", !arbeitet && agenten_hier.length > 0);
      live_feld = feld.querySelector(".label_live");
      if (live_feld) {
        live_text = text_der_arbeit(agenten_hier, bilder[i].knoten);
        if (live_feld.textContent !== live_text) {
          live_feld.textContent = live_text;
        }
      }
    }
    bilder[i].knoten.sx = bilder[i].bild.sx;
    bilder[i].knoten.sy = bilder[i].bild.sy;
    bilder[i].knoten.sr = radius;
  }
}

function passe_leinwand() {
  var leinwand = document.querySelector("#buehne");
  var mass = buehnen_mass();
  var rate = window.devicePixelRatio || 1;
  if (mass.breite < 2 || mass.hoehe < 2) {
    return;
  }
  leinwand.width = Math.round(mass.breite * rate);
  leinwand.height = Math.round(mass.hoehe * rate);
  leinwand.style.width = mass.breite + "px";
  leinwand.style.height = mass.hoehe + "px";
  leinwand.getContext("2d").setTransform(rate, 0, 0, rate, 0, 0);
}

function maus_auf_buehne(ereignis) {
  var rect = document.querySelector("#buehne").getBoundingClientRect();
  return {x: ereignis.clientX - rect.left, y: ereignis.clientY - rect.top};
}

function treffer(x, y) {
  var i;
  var beste = null;
  var dx;
  var dy;
  var abstand_px;
  for (i = 0; i < knoten.length; i++) {
    dx = knoten[i].sx - x;
    dy = knoten[i].sy - y;
    abstand_px = Math.sqrt(dx * dx + dy * dy);
    if (abstand_px <= knoten[i].sr + 10) {
      if (!beste || knoten[i].sr < beste.sr) {
        beste = knoten[i];
      }
    }
  }
  return beste;
}

function starte_schieben(id, x, y) {
  schiebt = true;
  schiebe_id = id;
  hat_gezogen = false;
  letzter_x = x;
  letzter_y = y;
  start_x = x;
  start_y = y;
  document.querySelector("#buehne").classList.add("schiebt");
}

function loslassen() {
  if (schiebt && !hat_gezogen && schiebe_id) {
    waehle(schiebe_id);
  }
  schiebt = false;
  schiebe_id = "";
  zieht = false;
  document.querySelector("#buehne").classList.remove("schiebt");
  document.querySelector("#buehne").classList.remove("zieht");
}

function binde_maus() {
  var leinwand = document.querySelector("#buehne");
  leinwand.addEventListener("pointerdown", function (ereignis) {
    var punkt = maus_auf_buehne(ereignis);
    var ziel = treffer(punkt.x, punkt.y);
    if (ziel) {
      starte_schieben(ziel.id, ereignis.clientX, ereignis.clientY);
      return;
    }
    zieht = true;
    letzter_x = ereignis.clientX;
    letzter_y = ereignis.clientY;
    leinwand.classList.add("zieht");
  });
  window.addEventListener("pointermove", function (ereignis) {
    var dx;
    var dy;
    if (schiebt) {
      dx = ereignis.clientX - letzter_x;
      dy = ereignis.clientY - letzter_y;
      if (Math.abs(ereignis.clientX - start_x) + Math.abs(ereignis.clientY - start_y) > 5) {
        hat_gezogen = true;
      }
      schiebe_welt(schiebe_id, dx, dy);
      letzter_x = ereignis.clientX;
      letzter_y = ereignis.clientY;
      return;
    }
    if (!zieht) {
      return;
    }
    yaw += (ereignis.clientX - letzter_x) * 0.005;
    pitch += (ereignis.clientY - letzter_y) * 0.005;
    pitch = Math.max(-1.1, Math.min(1.1, pitch));
    yaw_tempo = (ereignis.clientX - letzter_x) * 0.0002;
    pitch_tempo = (ereignis.clientY - letzter_y) * 0.0002;
    letzter_x = ereignis.clientX;
    letzter_y = ereignis.clientY;
  });
  window.addEventListener("pointerup", loslassen);
  leinwand.addEventListener("wheel", function (ereignis) {
    ereignis.preventDefault();
    abstand += ereignis.deltaY * 0.002;
    abstand = Math.max(3.2, Math.min(8, abstand));
  }, {passive: false});
}

function rahmen() {
  if (!zieht && !schiebt) {
    yaw += yaw_tempo;
    pitch += pitch_tempo;
    yaw_tempo *= 0.96;
    pitch_tempo *= 0.96;
    if (dreh_stopp) {
      yaw_tempo = 0;
      pitch_tempo = 0;
    } else if (Math.abs(yaw_tempo) < 0.0008) {
      yaw_tempo = 0.0008;
    }
  }
  laufzeit += 0.016;
  zeichne_szene();
  requestAnimationFrame(rahmen);
}

function punkt_klasse(zustand) {
  if (zustand === "fertig") {
    return "fertig";
  }
  if (zustand === "laeuft") {
    return "laeuft";
  }
  if (zustand === "wartet" || zustand === "pr-offen") {
    return "wartet";
  }
  if (zustand === "fehler") {
    return "fehler";
  }
  if (zustand === "fehlt") {
    return "fehlt";
  }
  return "leer";
}

function zeit_kurz(wert) {
  if (!wert) {
    return "—";
  }
  if (wert.length >= 16) {
    return wert.slice(11, 16);
  }
  return wert;
}

function satz_von(eintrag, name) {
  var agenten = name ? letzte_agenten(name) : [];
  var live;
  var looptext = loop_satz(eintrag);
  if (looptext && !agenten.length) {
    return kuerze(looptext, 90);
  }
  if (eintrag && eintrag.stand_text && !agenten.length) {
    return kuerze(eintrag.stand_text, 90);
  }
  if (agenten.length) {
    live = text_der_arbeit(agenten, null).replace(/\n/g, " · ");
    return kuerze(live, 90);
  }
  if (!eintrag) {
    return "kein stand";
  }
  if (eintrag.letzter_auftrag) {
    return kuerze(eintrag.zustand + " · " + eintrag.letzter_auftrag, 90);
  }
  if (eintrag.zustand === "fehlt") {
    return "ordner fehlt";
  }
  if (eintrag.zustand && eintrag.zustand !== "leer") {
    return eintrag.zustand;
  }
  return "noch kein lauf";
}

function zaehle_zustaende(projekte) {
  var n = {laeuft: 0, fertig: 0};
  var name;
  for (name in projekte) {
    if (!Object.prototype.hasOwnProperty.call(projekte, name)) {
      continue;
    }
    if (projekte[name].zustand === "laeuft" || projekte[name].zustand === "wartet" || laufende_agenten(name).length) {
      n.laeuft += 1;
    }
    if (projekte[name].zustand === "fertig" || projekte[name].zustand === "pr-offen") {
      n.fertig += 1;
    }
  }
  return n;
}

function zeichne_zaehler(projekte) {
  var box = document.querySelector("#zaehler");
  var n = zaehle_zustaende(projekte || {});
  var a;
  var b;
  box.textContent = "";
  a = document.createElement("span");
  a.className = "chip laeuft";
  a.textContent = n.laeuft + " laufen";
  b = document.createElement("span");
  b.className = "chip fertig";
  b.textContent = n.fertig + " fertig";
  box.appendChild(a);
  box.appendChild(b);
}

function sende_dev_auftrag(daten) {
  return fetch("/dev/auftrag", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(daten)
  }).then(function (antwort) {
    return antwort.json().then(function (body) {
      return {ok: antwort.ok, body: body};
    });
  });
}

function sende_anhalten(projekt) {
  return fetch("/dev/anhalten", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({projekt: projekt})
  }).then(function (antwort) {
    return antwort.json().then(function (body) {
      return {ok: antwort.ok, body: body};
    });
  });
}

function mach_pill(text, handler) {
  var knopf = document.createElement("button");
  knopf.type = "button";
  knopf.className = "pill";
  knopf.draggable = false;
  knopf.textContent = text;
  knopf.addEventListener("pointerdown", function (ereignis) {
    ereignis.stopPropagation();
  });
  knopf.addEventListener("click", function (ereignis) {
    ereignis.stopPropagation();
    handler();
  });
  return knopf;
}

function hole_anordnung() {
  return fetch("/maske/anordnung")
    .then(function (antwort) {
      if (!antwort.ok) {
        throw new Error("anordnung");
      }
      return antwort.json();
    })
    .then(function (daten) {
      anordnung = {
        eintraege: Array.isArray(daten && daten.eintraege) ? daten.eintraege : []
      };
      anordnung_geladen = true;
      karten_sig = "";
      zeichne_karten();
    })
    .catch(function () {
      anordnung = {eintraege: []};
      anordnung_geladen = true;
      karten_sig = "";
      zeichne_karten();
    });
}

function speichere_anordnung() {
  if (speicher_timer) {
    clearTimeout(speicher_timer);
  }
  speicher_timer = setTimeout(function () {
    fetch("/maske/anordnung", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        eintraege: anordnung.eintraege.map(function (e) {
          return {id: e.id, typ: e.typ, gruppe: e.gruppe};
        })
      })
    }).catch(function () {
      setze_hinweis("anordnung nicht gespeichert");
    });
  }, 200);
}

function finde_anordnung(id) {
  var i;
  for (i = 0; i < anordnung.eintraege.length; i++) {
    if (anordnung.eintraege[i].id === id) {
      return anordnung.eintraege[i];
    }
  }
  return null;
}

function sync_anordnung(projekte, agenten) {
  //bekannte behalten, neue hinten; nichts loeschen bevor daten da sind
  var map = {};
  var i;
  var name;
  var agent;
  var eid;
  var projekt_namen = Object.keys(projekte || {});
  var hat_projekte = projekt_namen.length > 0;
  var hat_agenten = (agenten || []).length > 0;
  if (!hat_projekte && !hat_agenten) {
    return;
  }
  for (i = 0; i < anordnung.eintraege.length; i++) {
    map[anordnung.eintraege[i].id] = anordnung.eintraege[i];
  }
  for (i = 0; i < projekt_namen.length; i++) {
    name = projekt_namen[i];
    if (map[name]) {
      map[name].typ = "projekt";
    } else {
      anordnung.eintraege.push({id: name, typ: "projekt", gruppe: "projekte"});
      map[name] = anordnung.eintraege[anordnung.eintraege.length - 1];
    }
  }
  for (i = 0; i < (agenten || []).length; i++) {
    agent = agenten[i];
    eid = agent.id || "";
    if (!eid) {
      continue;
    }
    if (map[eid]) {
      map[eid].typ = "dienst";
    } else {
      anordnung.eintraege.push({id: eid, typ: "dienst", gruppe: "dienste"});
      map[eid] = anordnung.eintraege[anordnung.eintraege.length - 1];
    }
  }
}

function eintraege_fuer(gruppe) {
  var liste = [];
  var i;
  var e;
  for (i = 0; i < anordnung.eintraege.length; i++) {
    e = anordnung.eintraege[i];
    if (e.gruppe === gruppe) {
      liste.push(e);
    }
  }
  return liste;
}

function filter_treffer(text) {
  var suche = (document.querySelector("#suche").value || "").trim().toLowerCase();
  if (!suche) {
    return true;
  }
  return String(text || "").toLowerCase().indexOf(suche) >= 0;
}

function mach_griff(karte) {
  var griff = document.createElement("div");
  var punkte = document.createElement("span");
  griff.className = "griff";
  griff.title = "ziehen";
  griff.setAttribute("aria-hidden", "true");
  punkte.className = "griff_punkte";
  griff.appendChild(punkte);
  griff.addEventListener("pointerdown", function () {
    ziehe_von_griff = true;
    karte.draggable = true;
  });
  return griff;
}

function binde_karte_drag(karte) {
  karte.addEventListener("dragstart", function (ereignis) {
    if (!ziehe_von_griff) {
      ereignis.preventDefault();
      return;
    }
    karte.classList.add("zieht");
    ereignis.dataTransfer.effectAllowed = "move";
    ereignis.dataTransfer.setData("text/plain", karte.getAttribute("data-id") || "");
    ereignis.dataTransfer.setData("application/x-maske-id", karte.getAttribute("data-id") || "");
  });
  karte.addEventListener("dragend", function () {
    ziehe_von_griff = false;
    karte.draggable = false;
    karte.classList.remove("zieht");
    entferne_platzhalter();
    document.querySelectorAll(".gruppe_box.ziel").forEach(function (box) {
      box.classList.remove("ziel");
    });
  });
}

function entferne_platzhalter() {
  document.querySelectorAll(".platzhalter").forEach(function (el) {
    el.remove();
  });
}

function setze_platzhalter(box, vor_karte) {
  var linie = document.createElement("div");
  linie.className = "platzhalter";
  entferne_platzhalter();
  if (vor_karte) {
    box.insertBefore(linie, vor_karte);
  } else {
    box.appendChild(linie);
  }
}

function finde_drop_karte(box, client_y) {
  var karten = Array.prototype.slice.call(box.querySelectorAll(".karte:not(.zieht)"));
  var i;
  var rect;
  for (i = 0; i < karten.length; i++) {
    rect = karten[i].getBoundingClientRect();
    if (client_y < rect.top + rect.height / 2) {
      return karten[i];
    }
  }
  return null;
}

function binde_gruppe_drop(box) {
  box.addEventListener("dragover", function (ereignis) {
    var ziel;
    ereignis.preventDefault();
    ereignis.dataTransfer.dropEffect = "move";
    box.classList.add("ziel");
    ziel = finde_drop_karte(box, ereignis.clientY);
    setze_platzhalter(box, ziel);
  });
  box.addEventListener("dragleave", function (ereignis) {
    if (!box.contains(ereignis.relatedTarget)) {
      box.classList.remove("ziel");
      entferne_platzhalter();
    }
  });
  box.addEventListener("drop", function (ereignis) {
    var id = ereignis.dataTransfer.getData("application/x-maske-id") || ereignis.dataTransfer.getData("text/plain");
    var gruppe = box.getAttribute("data-gruppe");
    var vor = finde_drop_karte(box, ereignis.clientY);
    var vor_id = vor ? vor.getAttribute("data-id") : "";
    ereignis.preventDefault();
    box.classList.remove("ziel");
    entferne_platzhalter();
    if (!id || !gruppe) {
      return;
    }
    verschiebe_eintrag(id, gruppe, vor_id);
  });
}

function verschiebe_eintrag(id, ziel_gruppe, vor_id) {
  var eintrag = finde_anordnung(id);
  var rest = [];
  var i;
  var ziel_liste;
  var eingefuegt = false;
  if (!eintrag) {
    return;
  }
  eintrag.gruppe = ziel_gruppe;
  for (i = 0; i < anordnung.eintraege.length; i++) {
    if (anordnung.eintraege[i].id !== id) {
      rest.push(anordnung.eintraege[i]);
    }
  }
  ziel_liste = [];
  for (i = 0; i < rest.length; i++) {
    if (rest[i].gruppe === ziel_gruppe) {
      if (vor_id && rest[i].id === vor_id && !eingefuegt) {
        ziel_liste.push(eintrag);
        eingefuegt = true;
      }
      ziel_liste.push(rest[i]);
    }
  }
  if (!eingefuegt) {
    ziel_liste.push(eintrag);
  }
  anordnung.eintraege = baue_reihenfolge_nach_drop(rest, ziel_gruppe, ziel_liste);
  karten_sig = "";
  zeichne_karten();
  speichere_anordnung();
}

function baue_reihenfolge_nach_drop(rest_ohne_gezogen, ziel_gruppe, ziel_liste) {
  //zielgruppe durch neue liste ersetzen, rest bleibt
  var neu = [];
  var gesehen_ziel = false;
  var i;
  for (i = 0; i < rest_ohne_gezogen.length; i++) {
    if (rest_ohne_gezogen[i].gruppe === ziel_gruppe) {
      if (!gesehen_ziel) {
        neu = neu.concat(ziel_liste);
        gesehen_ziel = true;
      }
    } else {
      neu.push(rest_ohne_gezogen[i]);
    }
  }
  if (!gesehen_ziel) {
    neu = neu.concat(ziel_liste);
  }
  return neu;
}

function mach_projekt_karte(name, eintrag) {
  var karte = document.createElement("article");
  var inhalt = document.createElement("div");
  var knopf;
  var text;
  var kopf;
  var name_el;
  var zeit_el;
  var satz_el;
  var pills;
  var sichtbar = letzte_agenten(name);
  var stand_text = satz_von(eintrag, name);
  karte.className = "karte" + (gewaehlt === name ? " gewaehlt" : "");
  karte.setAttribute("data-id", name);
  karte.setAttribute("data-typ", "projekt");
  karte.setAttribute("data-pfad", (eintrag && eintrag.pfad) || name);
  karte.appendChild(mach_griff(karte));
  inhalt.className = "karte_inhalt";
  knopf = document.createElement("button");
  knopf.type = "button";
  knopf.className = "zeile";
  knopf.setAttribute("data-id", name);
  knopf.draggable = false;
  text = document.createElement("span");
  text.className = "punkt " + (laufende_agenten(name).length ? "laeuft" : (sichtbar.length ? (sichtbar[0].stand === "problem" ? "fehler" : punkt_klasse(sichtbar[0].stand)) : punkt_klasse((eintrag && eintrag.zustand) || "leer")));
  knopf.appendChild(text);
  text = document.createElement("span");
  text.className = "zeile_text";
  kopf = document.createElement("span");
  kopf.className = "zeile_kopf";
  name_el = document.createElement("span");
  name_el.className = "name";
  name_el.textContent = name;
  kopf.appendChild(name_el);
  zeit_el = document.createElement("span");
  zeit_el.className = "zeit";
  zeit_el.textContent = zeit_kurz((eintrag && (eintrag.ende || eintrag.start)) || "");
  kopf.appendChild(zeit_el);
  text.appendChild(kopf);
  satz_el = document.createElement("span");
  satz_el.className = "satz";
  satz_el.textContent = stand_text;
  text.appendChild(satz_el);
  knopf.appendChild(text);
  knopf.addEventListener("pointerdown", function (ereignis) {
    ereignis.stopPropagation();
  });
  knopf.addEventListener("click", function (ereignis) {
    waehle(ereignis.currentTarget.getAttribute("data-id"));
  });
  inhalt.appendChild(knopf);
  pills = document.createElement("div");
  pills.className = "pills";
  pills.appendChild(mach_pill("pflegen", function () {
    sende_dev_auftrag({projekt: name, auftrag: "pflege " + name, modus: "vorschlagen"}).then(function (antwort) {
      setze_hinweis(antwort.ok ? "pflege eingereiht · " + name : ((antwort.body && antwort.body.fehler) || "fehler"));
      hole_dev_status();
    }).catch(function () {
      setze_hinweis("auftrag nicht angekommen");
    });
  }));
  pills.appendChild(mach_pill("selber", function () {
    sende_dev_auftrag({projekt: name, auftrag: "pflege " + name, modus: "selber"}).then(function (antwort) {
      setze_hinweis(antwort.ok ? "selber eingereiht · " + name : ((antwort.body && antwort.body.fehler) || "fehler"));
      hole_dev_status();
    }).catch(function () {
      setze_hinweis("auftrag nicht angekommen");
    });
  }));
  pills.appendChild(mach_pill("anhalten", function () {
    sende_anhalten(name).then(function (antwort) {
      setze_hinweis(antwort.ok ? "angehalten · " + name : ((antwort.body && antwort.body.fehler) || "fehler"));
      hole_dev_status();
    }).catch(function () {
      setze_hinweis("anhalten fehlgeschlagen");
    });
  }));
  if (eintrag && eintrag.zentrale) {
    pills.appendChild(mach_pill("loop starten", function () {
      var autonom = (eintrag.zentrale.loop_modus || "") === "autonom";
      sende_loop_start(name, autonom).then(function (antwort) {
        setze_hinweis(antwort.ok ? "loop gestartet · " + name : ((antwort.body && antwort.body.fehler) || "fehler"));
        hole_zentrale();
      }).catch(function () {
        setze_hinweis("loop start nicht angekommen");
      });
    }));
    pills.appendChild(mach_pill("push anfragen", function () {
      sende_freigabe(name, "push", false).then(function (antwort) {
        setze_hinweis(antwort.ok ? "push wartet auf freigabe · " + name : ((antwort.body && antwort.body.fehler) || "fehler"));
        hole_zentrale();
      }).catch(function () {
        setze_hinweis("freigabe nicht angekommen");
      });
    }));
    if ((eintrag.zentrale.freigaben || []).some(function (f) { return f.stand === "wartet"; })) {
      pills.appendChild(mach_pill("git freigeben", function () {
        sende_freigabe(name, "push", true).then(function (antwort) {
          setze_hinweis(antwort.ok && antwort.body && antwort.body.ausgefuehrt ? "push ausgefuehrt · " + name : ((antwort.body && (antwort.body.fehler || antwort.body.hinweis)) || "nicht gepusht"));
          hole_zentrale();
        }).catch(function () {
          setze_hinweis("freigabe nicht angekommen");
        });
      }));
      pills.appendChild(mach_pill("ablehnen", function () {
        sende_freigabe(name, "ablehnen", false).then(function (antwort) {
          setze_hinweis(antwort.ok ? "freigabe abgelehnt · " + name : ((antwort.body && antwort.body.fehler) || "fehler"));
          hole_zentrale();
        }).catch(function () {
          setze_hinweis("ablehnen fehlgeschlagen");
        });
      }));
    }
  }
  inhalt.appendChild(pills);
  karte.appendChild(inhalt);
  karte.addEventListener("mouseenter", function (ereignis) {
    document.querySelector("#hover_info").textContent = ereignis.currentTarget.getAttribute("data-pfad") || "";
  });
  binde_karte_drag(karte);
  return karte;
}

function mach_eingriff(id, aktion) {
  return mach_pill(aktion, function () {
    fetch("/bruecke/eingriff", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({id: id, aktion: aktion})
    }).then(function (antwort) {
      return antwort.json();
    }).then(function (daten) {
      lage_text = "";
      zeige_lage(daten);
    }).catch(function () {
      setze_hinweis("eingriff nicht angekommen");
    });
  });
}

function mach_dienst_karte(agent) {
  var karte = document.createElement("article");
  var inhalt = document.createElement("div");
  var knopf;
  var text;
  var kopf;
  var satz;
  var pills;
  var status = agent.stand === "problem" ? "fehler" : (agent.stand === "angehalten" ? "wartet" : (agent.stand || "leer"));
  karte.className = "karte";
  karte.setAttribute("data-id", agent.id || "");
  karte.setAttribute("data-typ", "dienst");
  karte.setAttribute("data-pfad", agent.ort || "");
  karte.appendChild(mach_griff(karte));
  inhalt.className = "karte_inhalt";
  knopf = document.createElement("button");
  knopf.type = "button";
  knopf.className = "zeile";
  knopf.draggable = false;
  text = document.createElement("span");
  text.className = "punkt " + punkt_klasse(status);
  knopf.appendChild(text);
  text = document.createElement("span");
  text.className = "zeile_text";
  kopf = document.createElement("span");
  kopf.className = "zeile_kopf";
  satz = document.createElement("span");
  satz.className = "name";
  satz.textContent = agent.name || agent.id;
  kopf.appendChild(satz);
  satz = document.createElement("span");
  satz.className = "zeit";
  satz.textContent = agent.stand || "";
  kopf.appendChild(satz);
  text.appendChild(kopf);
  satz = document.createElement("span");
  satz.className = "satz";
  satz.textContent = kuerze(agent.tun || "kein stand", 90);
  text.appendChild(satz);
  knopf.appendChild(text);
  knopf.addEventListener("pointerdown", function (ereignis) {
    ereignis.stopPropagation();
  });
  knopf.addEventListener("click", function (ereignis) {
    ereignis.stopPropagation();
  });
  //detail-fenster nur per doppelklick, damit ziehen/einfachklick nichts oeffnet
  knopf.addEventListener("dblclick", function (ereignis) {
    ereignis.stopPropagation();
    oeffne_dienst(agent.id || "");
  });
  inhalt.appendChild(knopf);
  pills = document.createElement("div");
  pills.className = "pills";
  pills.appendChild(mach_eingriff(agent.id, "anhalten"));
  pills.appendChild(mach_eingriff(agent.id, "weiter"));
  inhalt.appendChild(pills);
  karte.appendChild(inhalt);
  karte.addEventListener("mouseenter", function (ereignis) {
    document.querySelector("#hover_info").textContent = ereignis.currentTarget.getAttribute("data-pfad") || "";
  });
  binde_karte_drag(karte);
  return karte;
}

function mach_gruppe(name, titel_zeigen) {
  var wrap = document.createElement("section");
  var titel;
  var box = document.createElement("div");
  wrap.className = "gruppe";
  wrap.setAttribute("data-gruppe", name);
  if (titel_zeigen) {
    titel = document.createElement("h3");
    titel.className = "gruppe_titel";
    titel.textContent = name;
    wrap.appendChild(titel);
  }
  box.className = "gruppe_box";
  box.setAttribute("data-gruppe", name);
  binde_gruppe_drop(box);
  wrap.appendChild(box);
  return {wrap: wrap, box: box};
}

function zeichne_gruppe_karten(box, gruppe, projekte, agenten_map) {
  var liste = eintraege_fuer(gruppe);
  var i;
  var e;
  var agent;
  var sichtbar = 0;
  var hinweis;
  for (i = 0; i < liste.length; i++) {
    e = liste[i];
    if (e.typ === "projekt") {
      if (!projekte[e.id]) {
        continue;
      }
      if (!filter_treffer(e.id + " " + satz_von(projekte[e.id], e.id))) {
        continue;
      }
      box.appendChild(mach_projekt_karte(e.id, projekte[e.id]));
      sichtbar += 1;
    } else if (e.typ === "dienst") {
      agent = agenten_map[e.id];
      if (!agent) {
        continue;
      }
      if (!filter_treffer((agent.tun || "") + " " + (agent.name || "") + " " + (agent.projekt || "") + " " + (agent.id || ""))) {
        continue;
      }
      box.appendChild(mach_dienst_karte(agent));
      sichtbar += 1;
    }
  }
  if (sichtbar === 0) {
    hinweis = document.createElement("p");
    hinweis.className = "leer_hinweis";
    hinweis.textContent = gruppe === "dienste" ? "keine dienste" : "kein treffer";
    box.appendChild(hinweis);
  }
}

function zeichne_karten() {
  var box = document.querySelector("#karten_liste");
  var projekte = alle_projekte();
  var agenten_map = {};
  var scroll = box.scrollTop;
  var sig;
  var i;
  var gruppe;
  var titel_zeigen;
  if (!anordnung_geladen) {
    return;
  }
  for (i = 0; i < lage_agenten.length; i++) {
    if (lage_agenten[i].id) {
      agenten_map[lage_agenten[i].id] = lage_agenten[i];
    }
  }
  sync_anordnung(projekte, lage_agenten);
  sig = JSON.stringify({
    tab: tab_aktiv,
    suche: (document.querySelector("#suche").value || "").trim().toLowerCase(),
    gewaehlt: gewaehlt,
    eintraege: anordnung.eintraege,
    projekte: Object.keys(projekte).sort().map(function (n) {
      return [n, projekte[n].zustand, projekte[n].letzter_auftrag, projekte[n].ende || projekte[n].start, projekte[n].pfad];
    }),
    dienste: lage_agenten.map(function (a) {
      return [a.id, a.stand, a.tun, a.ort, a.name];
    })
  });
  if (sig === karten_sig) {
    return;
  }
  karten_sig = sig;
  box.textContent = "";
  if (tab_aktiv === "alle") {
    gruppe = mach_gruppe("projekte", true);
    box.appendChild(gruppe.wrap);
    zeichne_gruppe_karten(gruppe.box, "projekte", projekte, agenten_map);
    gruppe = mach_gruppe("dienste", true);
    box.appendChild(gruppe.wrap);
    zeichne_gruppe_karten(gruppe.box, "dienste", projekte, agenten_map);
  } else {
    titel_zeigen = false;
    gruppe = mach_gruppe(tab_aktiv, titel_zeigen);
    box.appendChild(gruppe.wrap);
    zeichne_gruppe_karten(gruppe.box, tab_aktiv, projekte, agenten_map);
  }
  box.scrollTop = scroll;
}

function escape_html(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function inline_md(text) {
  var roh = escape_html(text);
  roh = roh.replace(/`([^`]+)`/g, "<code>$1</code>");
  roh = roh.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  roh = roh.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  return roh;
}

function render_md(text) {
  var zeilen = String(text || "").replace(/\r\n/g, "\n").split("\n");
  var html = [];
  var i;
  var zeile;
  var in_ul = false;
  function schliess_ul() {
    if (in_ul) {
      html.push("</ul>");
      in_ul = false;
    }
  }
  for (i = 0; i < zeilen.length; i++) {
    zeile = zeilen[i];
    if (/^###\s+/.test(zeile)) {
      schliess_ul();
      html.push("<h3>" + inline_md(zeile.replace(/^###\s+/, "")) + "</h3>");
      continue;
    }
    if (/^##\s+/.test(zeile)) {
      schliess_ul();
      html.push("<h3>" + inline_md(zeile.replace(/^##\s+/, "")) + "</h3>");
      continue;
    }
    if (/^#\s+/.test(zeile)) {
      schliess_ul();
      html.push("<h3>" + inline_md(zeile.replace(/^#\s+/, "")) + "</h3>");
      continue;
    }
    if (/^[-*]\s+/.test(zeile)) {
      if (!in_ul) {
        html.push("<ul>");
        in_ul = true;
      }
      html.push("<li>" + inline_md(zeile.replace(/^[-*]\s+/, "")) + "</li>");
      continue;
    }
    schliess_ul();
    if (!zeile.trim()) {
      html.push("<p></p>");
    } else {
      html.push("<p>" + inline_md(zeile) + "</p>");
    }
  }
  schliess_ul();
  return html.join("");
}

function protokoll_neueste_oben(text) {
  var roh = String(text || "").replace(/\r\n/g, "\n").trim();
  var teile;
  if (!roh) {
    return "";
  }
  if (roh.indexOf("\n## ") >= 0 || roh.indexOf("\n---") >= 0) {
    teile = roh.split(/\n(?=## )|\n(?=---)/);
    if (teile.length > 1) {
      return teile.reverse().join("\n");
    }
  }
  return roh;
}

function parse_wege(text) {
  var zeilen = String(text || "").split(/\r?\n/);
  var fund = [];
  var i;
  var m;
  for (i = 0; i < zeilen.length; i++) {
    m = zeilen[i].match(/^\s*(?:[-*]|\d+[.)])\s*(.+)$/);
    if (m && /weg|aufwand|vorschl|option|variante/i.test(zeilen[i])) {
      fund.push(m[1].trim());
    } else if (m && /^\s*\d+[.)]/.test(zeilen[i])) {
      fund.push(m[1].trim());
    }
  }
  return fund.slice(0, 8);
}

function zeichne_wege(id, text) {
  var box = document.querySelector("#vorschlag_liste");
  var wege;
  var i;
  var haken;
  var knopf;
  var schluessel;
  var leer;
  if (wege_fuer !== id) {
    vorschlag_haken = {};
    wege_fuer = id;
  }
  wege = parse_wege(text);
  wege_liste = wege;
  box.textContent = "";
  if (wege.length === 0) {
    leer = document.createElement("p");
    leer.className = "leer_hinweis";
    leer.textContent = "keine wege im protokoll";
    box.appendChild(leer);
    return;
  }
  for (i = 0; i < wege.length; i++) {
    schluessel = id + "|" + i;
    haken = document.createElement("label");
    haken.className = "haken";
    knopf = document.createElement("input");
    knopf.type = "checkbox";
    knopf.checked = !!vorschlag_haken[schluessel];
    knopf.setAttribute("data-schluessel", schluessel);
    knopf.setAttribute("data-index", String(i));
    knopf.addEventListener("change", function (ereignis) {
      var key = ereignis.currentTarget.getAttribute("data-schluessel");
      vorschlag_haken[key] = ereignis.currentTarget.checked;
    });
    haken.appendChild(knopf);
    haken.appendChild(document.createTextNode((i + 1) + ". " + wege[i]));
    box.appendChild(haken);
  }
}

function zeichne_panel(eintrag) {
  var meta = document.querySelector("#meta_zeilen");
  var name = gewaehlt;
  var zeilen;
  var i;
  var p;
  var span;
  var stark;
  var agenten;
  var agent;
  if (!name || name === "profil") {
    document.querySelector("#agent_name").textContent = name === "profil" ? "profil" : "keins gewaehlt";
    meta.textContent = "";
    meta.classList.remove("meta_laeuft");
    meta.classList.remove("meta_fertig");
    document.querySelector("#knopf_freigeben").disabled = true;
    leere_bericht();
    return;
  }
  document.querySelector("#agent_name").textContent = name;
  document.querySelector("#knopf_freigeben").disabled = false;
  agenten = letzte_agenten(name);
  if (agenten.length) {
    zeilen = [];
    for (i = 0; i < agenten.length; i++) {
      agent = agenten[i];
      zeilen.push(["agent", (agent.name || agent.id || "agent") + " · " + (agent.stand || "laeuft")]);
      zeilen.push(["macht", agent.tun || "—"]);
      if (agent.ort) {
        zeilen.push(["ort", agent.ort]);
      }
      if (agent.offen) {
        zeilen.push(["offen", agent.offen]);
      }
    }
  } else {
    zeilen = [
      ["zustand", (eintrag && eintrag.zustand) || "leer"],
      ["modus", (eintrag && eintrag.modus) || ((eintrag && eintrag.zentrale && eintrag.zentrale.loop_modus) || "—")],
      ["letzter auftrag", (eintrag && eintrag.letzter_auftrag) || "—"]
    ];
  }
  if (eintrag && eintrag.zentrale && eintrag.zentrale.loop_status) {
    var ls = eintrag.zentrale.loop_status;
    zeilen.push(["loop", loop_satz(eintrag) || (ls.phase || "—")]);
    if (ls.letzter_fehler) {
      zeilen.push(["loop-fehler", ls.letzter_fehler]);
    }
  }
  meta.classList.toggle("meta_laeuft", laufende_agenten(name).length > 0 || (eintrag && eintrag.zustand === "laeuft"));
  meta.classList.toggle("meta_fertig", laufende_agenten(name).length === 0 && agenten.length > 0 && agenten[0].stand === "fertig");
  meta.textContent = "";
  for (i = 0; i < zeilen.length; i++) {
    p = document.createElement("div");
    p.className = "meta_zeile";
    span = document.createElement("span");
    span.textContent = zeilen[i][0];
    stark = document.createElement("strong");
    stark.textContent = zeilen[i][1];
    p.appendChild(span);
    p.appendChild(stark);
    meta.appendChild(p);
  }
}

function leere_bericht() {
  bericht_sig = "";
  bericht_fuer = "";
  bericht_stand_text = "";
  bericht_naechstes_text = "";
  document.querySelector("#bericht_stand").textContent = "kein stand";
  document.querySelector("#bericht_gemacht").textContent = "—";
  document.querySelector("#bericht_aenderungen").textContent = "—";
  document.querySelector("#bericht_todos").textContent = "—";
  document.querySelector("#bericht_naechstes").textContent = "—";
}

function frische_gemacht() {
  var box = document.querySelector("#bericht_gemacht");
  var alt;
  var agenten;
  var i;
  var p;
  if (!box) {
    return;
  }
  alt = box.querySelectorAll(".arbeit_gemacht");
  for (i = 0; i < alt.length; i++) {
    alt[i].remove();
  }
  agenten = letzte_agenten(gewaehlt);
  for (i = agenten.length - 1; i >= 0; i--) {
    p = document.createElement("p");
    p.className = "arbeit_gemacht";
    p.textContent = (agenten[i].name || agenten[i].id || "agent") + " · " + (agenten[i].tun || "arbeitet");
    box.insertBefore(p, box.firstChild);
  }
  alt = box.querySelectorAll("li");
  for (i = 0; i < alt.length; i++) {
    if ((alt[i].textContent || "").indexOf("noch kein agent-lauf") === 0) {
      alt[i].style.display = agenten.length ? "none" : "";
    }
  }
}

function frische_live() {
  var stand = document.querySelector("#bericht_stand");
  var naechstes = document.querySelector("#bericht_naechstes");
  var agenten = letzte_agenten(gewaehlt);
  var teile = [];
  var i;
  var laeuft = false;
  frische_gemacht();
  if (!stand) {
    return;
  }
  if (!agenten.length) {
    if (bericht_stand_text) {
      stand.textContent = bericht_stand_text;
    }
    if (naechstes && bericht_naechstes_text) {
      naechstes.textContent = bericht_naechstes_text;
    }
    return;
  }
  for (i = 0; i < agenten.length; i++) {
    if (agenten[i].stand === "laeuft") {
      laeuft = true;
    }
    teile.push((agenten[i].name || agenten[i].id || "agent") + " " + (agenten[i].stand || "laeuft") + " · " + (agenten[i].tun || "arbeitet"));
  }
  stand.textContent = teile.join("\n");
  if (naechstes && laeuft) {
    naechstes.textContent = "lauf abwarten. " + (agenten[0].name || "agent") + " arbeitet gerade.";
  } else if (naechstes && agenten[0].offen) {
    naechstes.textContent = "offen: " + agenten[0].offen;
  }
}

function mach_bericht_liste(eintraege, map_fn) {
  var ul = document.createElement("ul");
  var i;
  var li;
  ul.className = "bericht_liste";
  if (!eintraege || eintraege.length === 0) {
    li = document.createElement("li");
    li.textContent = "—";
    ul.appendChild(li);
    return ul;
  }
  for (i = 0; i < eintraege.length; i++) {
    li = document.createElement("li");
    map_fn(li, eintraege[i], i);
    ul.appendChild(li);
  }
  return ul;
}

function zeige_bericht(daten) {
  var roh = JSON.stringify(daten || {});
  var stand = document.querySelector("#bericht_stand");
  var gemacht = document.querySelector("#bericht_gemacht");
  var aend = document.querySelector("#bericht_aenderungen");
  var todos = document.querySelector("#bericht_todos");
  var naechstes = document.querySelector("#bericht_naechstes");
  var git;
  var klein;
  if (roh === bericht_sig) {
    frische_live();
    return;
  }
  bericht_sig = roh;
  bericht_stand_text = (daten && daten.stand_jetzt && daten.stand_jetzt.text) || "kein stand";
  bericht_naechstes_text = (daten && daten.naechster_schritt) || "—";
  stand.textContent = bericht_stand_text;
  gemacht.textContent = "";
  gemacht.appendChild(mach_bericht_liste((daten && daten.zuletzt_gemacht) || [], function (li, eintrag) {
    li.textContent = eintrag.was || "—";
    if (eintrag.warum) {
      klein = document.createElement("span");
      klein.className = "bericht_klein";
      klein.textContent = "warum: " + eintrag.warum;
      li.appendChild(klein);
    }
  }));
  aend.textContent = "";
  git = (daten && daten.letzte_aenderungen) || {};
  klein = document.createElement("p");
  klein.className = "bericht_klein";
  klein.textContent = "branch " + (git.branch || "—") + " · ahead " + (git.ahead || 0) + " · behind " + (git.behind || 0) + (git.upstream ? " · " + git.upstream : "") + (git.remote ? "" : " · kein remote");
  aend.appendChild(klein);
  aend.appendChild(mach_bericht_liste(git.commits || [], function (li, commit) {
    li.textContent = (commit.hash || "") + " · " + (commit.datum || "") + " · " + (commit.autor ? commit.autor + " · " : "") + (commit.betreff || "");
  }));
  if (git.uncommittet && git.uncommittet.length) {
    klein = document.createElement("p");
    klein.className = "bericht_klein";
    klein.textContent = "uncommittet:";
    aend.appendChild(klein);
    aend.appendChild(mach_bericht_liste(git.uncommittet, function (li, name) {
      li.textContent = name;
    }));
  } else {
    klein = document.createElement("p");
    klein.className = "bericht_klein";
    klein.textContent = "uncommittet: keine";
    aend.appendChild(klein);
  }
  if (daten && daten.freigaben && daten.freigaben.length) {
    klein = document.createElement("p");
    klein.className = "bericht_klein";
    klein.textContent = "freigaben:";
    aend.appendChild(klein);
    aend.appendChild(mach_bericht_liste(daten.freigaben, function (li, fr) {
      li.textContent = (fr.aktion || "push") + " · " + (fr.stand || "") + " · " + (fr.branch || "");
    }));
  }
  if (daten && daten.loop_status) {
    klein = document.createElement("p");
    klein.className = "bericht_klein";
    klein.textContent = "loop: " + (
      (daten.loop_modus ? daten.loop_modus + " · " : "") +
      (daten.loop_status.phase || "—") +
      (daten.loop_status.aktuell ? " · jetzt " + daten.loop_status.aktuell : "") +
      (daten.loop_status.offen && daten.loop_status.offen.length ? " · offen " + daten.loop_status.offen.join(", ") : "") +
      (daten.loop_status.fertig && daten.loop_status.fertig.length ? " · fertig " + daten.loop_status.fertig.join(", ") : "") +
      (daten.loop_status.fragen && daten.loop_status.fragen.length ? " · fragen " + daten.loop_status.fragen.join(", ") : "") +
      (daten.loop_status.letzter_fehler ? " · " + daten.loop_status.letzter_fehler : "")
    );
    aend.appendChild(klein);
  }
  if (daten && daten.agenten && daten.agenten.length) {
    klein = document.createElement("p");
    klein.className = "bericht_klein";
    klein.textContent = "agenten:";
    aend.appendChild(klein);
    aend.appendChild(mach_bericht_liste(daten.agenten, function (li, ag) {
      li.textContent = (ag.art || "agent") + " · " + (ag.stand || "") + " · " + (ag.auftrag || ag.ziel || "");
    }));
  }
  todos.textContent = "";
  todos.appendChild(mach_bericht_liste((daten && daten.was_muss_gemacht_werden) || [], function (li, todo) {
    li.textContent = (todo.text || "—") + " · " + (todo.art || "vorschlag");
    if (todo.warum) {
      klein = document.createElement("span");
      klein.className = "bericht_klein";
      klein.textContent = "warum: " + todo.warum;
      li.appendChild(klein);
    }
  }));
  naechstes.textContent = bericht_naechstes_text;
  frische_live();
}

function hole_bericht() {
  var id = gewaehlt;
  if (!id || id === "profil") {
    leere_bericht();
    return;
  }
  fetch("/zentrale/stand?projekt=" + encodeURIComponent(id))
    .then(function (antwort) {
      if (antwort.ok) {
        return antwort.json();
      }
      return fetch("/dev/bericht?projekt=" + encodeURIComponent(id)).then(function (zweite) {
        if (!zweite.ok) {
          throw new Error("bericht");
        }
        return zweite.json();
      });
    })
    .then(zeige_bericht)
    .catch(function () {
      if (bericht_fuer === id) {
        document.querySelector("#bericht_stand").textContent = "bericht nicht erreichbar";
      }
    });
}

function schliesse_dienst() {
  var overlay = document.querySelector("#dienst_overlay");
  dienst_offen_id = "";
  if (overlay) {
    overlay.hidden = true;
  }
}

function zeichne_dienst_inhalt(daten) {
  var box = document.querySelector("#dienst_inhalt");
  var pills = document.querySelector("#dienst_pills");
  var link = document.querySelector("#dienst_tab_link");
  var i;
  var abschnitt;
  var h;
  var p;
  document.querySelector("#dienst_titel").textContent = daten.name || daten.id || "dienst";
  if (link) {
    link.href = "dienst.html?id=" + encodeURIComponent(daten.id || "");
  }
  box.textContent = "";
  function meta(label, wert) {
    var zeile = document.createElement("div");
    var span = document.createElement("span");
    var stark = document.createElement("strong");
    zeile.className = "meta_zeile";
    span.textContent = label;
    stark.textContent = wert || "—";
    zeile.appendChild(span);
    zeile.appendChild(stark);
    box.appendChild(zeile);
  }
  meta("status", daten.status);
  meta("seit", daten.seit || "—");
  meta("ort", daten.ort || "—");
  abschnitt = document.createElement("section");
  abschnitt.className = "dienst_abschnitt";
  h = document.createElement("h2");
  h.textContent = "letzte meldung";
  p = document.createElement("p");
  p.className = "dienst_text";
  p.textContent = daten.letzte_meldung || "—";
  abschnitt.appendChild(h);
  abschnitt.appendChild(p);
  box.appendChild(abschnitt);
  if (daten.verlauf && daten.verlauf.length) {
    for (i = 0; i < daten.verlauf.length; i++) {
      abschnitt = document.createElement("section");
      abschnitt.className = "dienst_abschnitt";
      h = document.createElement("h2");
      h.textContent = "verlauf";
      p = document.createElement("p");
      p.className = "dienst_text";
      p.textContent = daten.verlauf[i].text || "—";
      abschnitt.appendChild(h);
      abschnitt.appendChild(p);
      box.appendChild(abschnitt);
    }
  }
  abschnitt = document.createElement("section");
  abschnitt.className = "dienst_abschnitt";
  h = document.createElement("h2");
  h.textContent = "was als naechstes";
  p = document.createElement("p");
  p.className = "dienst_text";
  p.textContent = daten.naechstes || "—";
  abschnitt.appendChild(h);
  abschnitt.appendChild(p);
  box.appendChild(abschnitt);
  pills.textContent = "";
  pills.appendChild(mach_eingriff(daten.id, "anhalten"));
  pills.appendChild(mach_eingriff(daten.id, "weiter"));
}

function oeffne_dienst(id) {
  var overlay = document.querySelector("#dienst_overlay");
  if (!id || !overlay) {
    return;
  }
  dienst_offen_id = id;
  overlay.hidden = false;
  document.querySelector("#dienst_titel").textContent = "laden…";
  document.querySelector("#dienst_inhalt").textContent = "";
  document.querySelector("#dienst_tab_link").href = "dienst.html?id=" + encodeURIComponent(id);
  fetch("/dev/dienst?id=" + encodeURIComponent(id))
    .then(function (antwort) {
      return antwort.json().then(function (body) {
        return {ok: antwort.ok, body: body};
      });
    })
    .then(function (antwort) {
      if (dienst_offen_id !== id) {
        return;
      }
      if (!antwort.ok) {
        document.querySelector("#dienst_inhalt").textContent = (antwort.body && antwort.body.fehler) || "dienst ungueltig";
        return;
      }
      zeichne_dienst_inhalt(antwort.body);
    })
    .catch(function () {
      if (dienst_offen_id === id) {
        document.querySelector("#dienst_inhalt").textContent = "nicht erreichbar";
      }
    });
}

function waehle(id) {
  if (!id) {
    return;
  }
  gewaehlt = id;
  karten_sig = "";
  zeichne_karten();
  zeichne_panel(alle_projekte()[id] || null);
  if (protokoll_fuer !== id) {
    protokoll_sig = "";
    log_sig = "";
    bericht_sig = "";
    bericht_stand_text = "";
    bericht_naechstes_text = "";
    protokoll_fuer = id;
    log_fuer = id;
    bericht_fuer = id;
  }
  hole_protokoll();
  hole_log();
  hole_bericht();
}

function zeige_protokoll(daten) {
  var text = (daten && daten.text) || "";
  var feld = document.querySelector("#protokoll_live");
  var sortiert;
  if (!text) {
    text = "kein protokoll · " + ((daten && daten.erwartet) || ".dev/protokoll.md");
  }
  if (text === protokoll_sig) {
    return;
  }
  protokoll_sig = text;
  if ((daten && daten.text)) {
    sortiert = protokoll_neueste_oben(daten.text);
    feld.innerHTML = render_md(sortiert);
    zeichne_wege(gewaehlt, daten.text);
  } else {
    feld.textContent = text;
    zeichne_wege(gewaehlt, "");
  }
}

function zeige_log(daten) {
  var text = (daten && daten.text) || "";
  var feld = document.querySelector("#log_live");
  if (!text) {
    text = "kein log · " + ((daten && daten.erwartet) || ".dev/laeufe/");
  }
  if (text === log_sig) {
    return;
  }
  log_sig = text;
  feld.textContent = text;
}

function hole_protokoll() {
  var id = gewaehlt;
  if (!id || id === "profil") {
    zeige_protokoll({text: "", erwartet: ".dev/protokoll.md"});
    return;
  }
  fetch("/dev/protokoll?projekt=" + encodeURIComponent(id))
    .then(function (antwort) {
      if (!antwort.ok) {
        throw new Error("protokoll");
      }
      return antwort.json();
    })
    .then(zeige_protokoll)
    .catch(function () {
      zeige_protokoll({text: "", erwartet: id + "/.dev/protokoll.md"});
    });
}

function hole_log() {
  var id = gewaehlt;
  if (!id || id === "profil") {
    zeige_log({text: "", erwartet: ".dev/laeufe/"});
    return;
  }
  fetch("/dev/log?projekt=" + encodeURIComponent(id))
    .then(function (antwort) {
      if (!antwort.ok) {
        throw new Error("log");
      }
      return antwort.json();
    })
    .then(zeige_log)
    .catch(function () {
      zeige_log({text: "", erwartet: id + "/.dev/laeufe/"});
    });
}

function gib_frei() {
  var id = gewaehlt;
  var gewaehlt_wege = [];
  var i;
  var key;
  var auftrag;
  if (!id || id === "profil") {
    return;
  }
  for (i = 0; i < wege_liste.length; i++) {
    key = id + "|" + i;
    if (vorschlag_haken[key]) {
      gewaehlt_wege.push((i + 1) + ". " + wege_liste[i]);
    }
  }
  if (gewaehlt_wege.length === 0) {
    setze_hinweis("keinen weg ausgewaehlt");
    document.querySelector("#wahl_stand").textContent = "keinen weg ausgewaehlt";
    return;
  }
  auftrag = "pflege " + id + " · wege: " + gewaehlt_wege.join(" · ");
  sende_dev_auftrag({projekt: id, auftrag: auftrag, modus: "selber"}).then(function (antwort) {
    if (!antwort.ok) {
      document.querySelector("#wahl_stand").textContent = (antwort.body && antwort.body.fehler) || "freigabe fehlgeschlagen";
      return;
    }
    document.querySelector("#wahl_stand").textContent = "freigegeben · modus selber";
    setze_hinweis("freigegeben · " + id);
    hole_dev_status();
  }).catch(function () {
    document.querySelector("#wahl_stand").textContent = "freigabe nicht angekommen";
  });
}

function zeige_lage(daten) {
  var agenten = (daten && daten.agenten) || [];
  var roh = JSON.stringify(agenten);
  lage_agenten = agenten;
  if (roh !== lage_text) {
    lage_text = roh;
    karten_sig = "";
  }
  zeichne_karten();
  if (gewaehlt && gewaehlt !== "profil") {
    zeichne_panel(alle_projekte()[gewaehlt] || null);
  }
  frische_live();
}

function hole_lage() {
  fetch("/bruecke/lage.json")
    .then(function (antwort) {
      if (!antwort.ok) {
        throw new Error("lage");
      }
      return antwort.json();
    })
    .then(zeige_lage)
    .catch(function () {
      setze_hinweis("bruecke nicht erreichbar");
    });
}

function hole_dev_status() {
  fetch("/dev/status")
    .then(function (antwort) {
      if (!antwort.ok) {
        throw new Error("dev-status");
      }
      return antwort.json();
    })
    .then(function (daten) {
      window.dev_status = daten || {};
      zeichne_nach_stand();
    })
    .catch(function () {
      return;
    });
}

function setze_tab(name) {
  var tabs = document.querySelectorAll("#tabs .tab");
  var i;
  tab_aktiv = name;
  for (i = 0; i < tabs.length; i++) {
    tabs[i].classList.toggle("gesetzt", tabs[i].getAttribute("data-tab") === name);
    tabs[i].setAttribute("aria-selected", tabs[i].getAttribute("data-tab") === name ? "true" : "false");
  }
  document.querySelector("#hover_info").textContent = hover_standard();
  karten_sig = "";
  zeichne_karten();
}

function starte_ansicht() {
  var tabs;
  var i;
  var overlay;
  window.dev_status = {projekte: {}};
  document.querySelector("#knopf_freigeben").addEventListener("click", gib_frei);
  document.querySelector("#suche").addEventListener("input", function () {
    karten_sig = "";
    zeichne_karten();
  });
  tabs = document.querySelectorAll("#tabs .tab");
  for (i = 0; i < tabs.length; i++) {
    tabs[i].addEventListener("click", function (ereignis) {
      setze_tab(ereignis.currentTarget.getAttribute("data-tab"));
    });
  }
  document.querySelector("#karten_liste").addEventListener("mouseleave", function () {
    document.querySelector("#hover_info").textContent = hover_standard();
  });
  overlay = document.querySelector("#dienst_overlay");
  document.querySelector("#dienst_schliessen").addEventListener("click", schliesse_dienst);
  overlay.addEventListener("click", function (ereignis) {
    if (ereignis.target === overlay) {
      schliesse_dienst();
    }
  });
  document.querySelector("#dienst_fenster").addEventListener("click", function (ereignis) {
    ereignis.stopPropagation();
  });
  window.addEventListener("keydown", function (ereignis) {
    if (ereignis.key === "Escape") {
      schliesse_dienst();
    }
  });
  passe_leinwand();
  window.addEventListener("resize", passe_leinwand);
  if (window.ResizeObserver) {
    new ResizeObserver(passe_leinwand).observe(document.querySelector("#mitte"));
  }
  binde_maus();
  setze_tab(tab_aktiv);
  hole_anordnung().then(function () {
    hole_lage();
    hole_dev_status();
    hole_zentrale();
  });
  setInterval(hole_lage, 3000);
  setInterval(hole_dev_status, 3000);
  setInterval(hole_zentrale, 3000);
  setInterval(hole_protokoll, 3000);
  setInterval(hole_log, 3000);
  setInterval(hole_bericht, 5000);
  requestAnimationFrame(rahmen);
}

starte_ansicht();

//drehung an/aus, merkt sich die wahl lokal im browser
var dreh_stopp = false;
try { dreh_stopp = window.localStorage.getItem("dreh_stopp") === "1"; } catch (e) { dreh_stopp = false; }
function zeige_dreh_knopf() {
  var k = document.querySelector("#dreh_knopf");
  if (!k) { return; }
  k.textContent = dreh_stopp ? "\u25B6" : "\u23F8";
  k.title = dreh_stopp ? "drehung starten" : "drehung stoppen";
  k.setAttribute("aria-pressed", dreh_stopp ? "true" : "false");
}
document.addEventListener("DOMContentLoaded", function () {
  var k = document.querySelector("#dreh_knopf");
  if (!k) { return; }
  zeige_dreh_knopf();
  k.addEventListener("click", function () {
    dreh_stopp = !dreh_stopp;
    try { window.localStorage.setItem("dreh_stopp", dreh_stopp ? "1" : "0"); } catch (e) {}
    zeige_dreh_knopf();
  });
});
