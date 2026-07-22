/**
 * Denní záloha dat aplikace RDS/DSPS z Firebase na Google Disk.
 * Stáhne CELOU databázi (stavby + objekty + inbox + log) jako jeden JSON s datem v názvu.
 * Běží v cloudu (bez zapnutého PC).
 *
 * Přidej do STEJNÉHO Apps Script projektu jako zálohy poptávek/ZBV
 * (účet popobjmsilniceozjih@gmail.com). Vlož, uprav 3 hodnoty níže (FB_DB, FB_KEY, FB_PASS)
 * a jednorázově spusť nastavTriggerZalohaRDS() — nastaví denní časovač ~4:15.
 * Poprvé spusť zalohaRDS() ručně a klikni „Povolit".
 *
 * OBNOVA: nejnovější rds-zaloha-*.json ze složky nahraj zpět do Firebase
 *         (PUT na FB_DB/.json?auth=<token>) — udělá Claude na požádání.
 */
var RDS_FOLDER_ID = '';  // <-- ID složky „RDS DSPS – zálohy" na Disku (necháš prázdné = vytvoří se sama)
var RDS_FB_DB   = 'https://ZMEN-projekt-default-rtdb.europe-west1.firebasedatabase.app';
var RDS_FB_KEY  = 'ZMEN-apiKey';
var RDS_FB_EMAIL= 'priprava@msilnice.cz';
var RDS_FB_PASS = 'ZMEN-heslo';
var RDS_KEEP_DAYS = 120;

function zalohaRDS() {
  try { ensureRdsTrigger_(); } catch (e) {}
  var token = rdsSignIn_();
  var resp = UrlFetchApp.fetch(RDS_FB_DB + '/.json?auth=' + token, { muteHttpExceptions: true });
  if (resp.getResponseCode() !== 200) {
    Logger.log('CHYBA stažení DB: ' + resp.getResponseCode() + ' ' + resp.getContentText().slice(0, 200));
    return;
  }
  var json = resp.getContentText();
  if (!json || json === 'null' || json.length < 5) { Logger.log('Prázdná DB – záloha přeskočena.'); return; }
  var folder = rdsFolder_();
  var stamp = Utilities.formatDate(new Date(), 'Europe/Prague', 'yyyy-MM-dd_HH-mm');
  folder.createFile('rds-zaloha-' + stamp + '.json', json, 'application/json');
  Logger.log('Záloha uložena: rds-zaloha-' + stamp + '.json (' + json.length + ' B)');
  rdsSmazStare_(folder);
}

function rdsFolder_() {
  if (RDS_FOLDER_ID) return DriveApp.getFolderById(RDS_FOLDER_ID);
  var it = DriveApp.getFoldersByName('RDS DSPS – zálohy');
  return it.hasNext() ? it.next() : DriveApp.createFolder('RDS DSPS – zálohy');
}
function rdsSignIn_() {
  var r = UrlFetchApp.fetch(
    'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=' + RDS_FB_KEY,
    { method: 'post', contentType: 'application/json',
      payload: JSON.stringify({ email: RDS_FB_EMAIL, password: RDS_FB_PASS, returnSecureToken: true }) });
  return JSON.parse(r.getContentText()).idToken;
}
function rdsSmazStare_(folder) {
  var hranice = new Date().getTime() - RDS_KEEP_DAYS * 24 * 60 * 60 * 1000;
  var files = folder.getFiles();
  while (files.hasNext()) {
    var f = files.next();
    if (f.getName().indexOf('rds-zaloha-') === 0 && f.getDateCreated().getTime() < hranice) f.setTrashed(true);
  }
}
function ensureRdsTrigger_() {
  var has = ScriptApp.getProjectTriggers().some(function (t) { return t.getHandlerFunction() === 'zalohaRDS'; });
  if (!has) ScriptApp.newTrigger('zalohaRDS').timeBased().atHour(4).nearMinute(15).everyDays(1).create();
}
function nastavTriggerZalohaRDS() {
  ScriptApp.getProjectTriggers().forEach(function (tr) { if (tr.getHandlerFunction() === 'zalohaRDS') ScriptApp.deleteTrigger(tr); });
  ScriptApp.newTrigger('zalohaRDS').timeBased().atHour(4).nearMinute(15).everyDays(1).create();
  Logger.log('Denní časovač zálohy RDS nastaven (~4:15).');
}
