from flask import Flask, render_template, request, jsonify, session
import sqlite3, os, hashlib, secrets
from datetime import datetime, timedelta

BASE=os.path.dirname(__file__); DB=os.path.join(BASE,'parking.db')
app=Flask(__name__); app.secret_key=os.environ.get('SECRET_KEY','change-this-demo-secret')

def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init_db():
 c=db(); q=c.cursor()
 q.executescript('''
 CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,phone TEXT,role TEXT NOT NULL DEFAULT 'DRIVER',license_number TEXT,admin_level TEXT);
 CREATE TABLE IF NOT EXISTS parking_lots(lot_id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,location TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS parking_floors(floor_id INTEGER PRIMARY KEY AUTOINCREMENT,lot_id INTEGER NOT NULL REFERENCES parking_lots,floor_number INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS parking_slots(slot_id INTEGER PRIMARY KEY AUTOINCREMENT,floor_id INTEGER NOT NULL REFERENCES parking_floors,slot_number TEXT NOT NULL,slot_type TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'AVAILABLE');
 CREATE TABLE IF NOT EXISTS vehicles(vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users,registration_number TEXT UNIQUE NOT NULL,vehicle_type TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS reservations(reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users,vehicle_id INTEGER NOT NULL REFERENCES vehicles,slot_id INTEGER NOT NULL REFERENCES parking_slots,booking_time TEXT NOT NULL,start_time TEXT NOT NULL,end_time TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'CONFIRMED');
 CREATE TABLE IF NOT EXISTS sessions(session_id INTEGER PRIMARY KEY AUTOINCREMENT,reservation_id INTEGER REFERENCES reservations,vehicle_id INTEGER NOT NULL REFERENCES vehicles,slot_id INTEGER NOT NULL REFERENCES parking_slots,entry_time TEXT NOT NULL,exit_time TEXT,fee REAL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS payments(payment_id INTEGER PRIMARY KEY AUTOINCREMENT,session_id INTEGER NOT NULL REFERENCES sessions,amount REAL NOT NULL,payment_time TEXT NOT NULL,status TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS notifications(notification_id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users,message TEXT NOT NULL,sent_at TEXT NOT NULL,is_read INTEGER DEFAULT 0);
 CREATE TABLE IF NOT EXISTS gates(gate_id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,status TEXT DEFAULT 'CLOSED');
 ''')
 if q.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0:
  q.execute('INSERT INTO users(name,email,password_hash,phone,role,admin_level) VALUES(?,?,?,?,?,?)',('Parking Admin','admin@parking.local',hashlib.sha256('admin123'.encode()).hexdigest(),'9999999999','ADMIN','SUPER'))
  q.execute('INSERT INTO users(name,email,password_hash,phone,role,license_number) VALUES(?,?,?,?,?,?)',('Demo Driver','driver@parking.local',hashlib.sha256('driver123'.encode()).hexdigest(),'9876543210','DRIVER','KA0120200001234'))
  q.execute('INSERT INTO parking_lots(name,location) VALUES(?,?)',('Central Parking','MG Road, Bengaluru'))
  lot=q.lastrowid
  for fl in range(1,3):
   q.execute('INSERT INTO parking_floors(lot_id,floor_number) VALUES(?,?)',(lot,fl)); floor=q.lastrowid
   for n in range(1,9): q.execute('INSERT INTO parking_slots(floor_id,slot_number,slot_type,status) VALUES(?,?,?,?)',(floor,f'F{fl}-{n:02}', 'BIKE' if n%4==0 else 'CAR','AVAILABLE'))
  q.execute('INSERT INTO gates(name,status) VALUES(?,?)',('Main Entry','CLOSED')); q.execute('INSERT INTO gates(name,status) VALUES(?,?)',('Main Exit','CLOSED'))
 c.commit(); c.close()

@app.route('/')
def home(): return render_template('index.html')
@app.route('/api/login',methods=['POST'])
def login():
 d=request.json or {}; c=db(); u=c.execute('SELECT * FROM users WHERE email=? AND password_hash=?',(d.get('email','').lower(),hashlib.sha256(d.get('password','').encode()).hexdigest())).fetchone(); c.close()
 if not u:return jsonify(error='Invalid email or password'),401
 session['uid']=u['user_id']; return jsonify(id=u['user_id'],name=u['name'],role=u['role'])
@app.route('/api/logout',methods=['POST'])
def logout(): session.clear(); return jsonify(ok=True)
def current(c):
 if not session.get('uid'): return None
 return c.execute('SELECT * FROM users WHERE user_id=?',(session['uid'],)).fetchone()
@app.route('/api/me')
def me():
 c=db(); u=current(c); c.close(); return jsonify(user=dict(id=u['user_id'],name=u['name'],role=u['role']) if u else None)
@app.route('/api/register',methods=['POST'])
def register():
 d=request.json or {}; c=db()
 try:
  c.execute('INSERT INTO users(name,email,password_hash,phone,role,license_number) VALUES(?,?,?,?,?,?)',(d['name'],d['email'].lower(),hashlib.sha256(d['password'].encode()).hexdigest(),d.get('phone'),'DRIVER',d.get('license'))); c.commit(); return jsonify(ok=True)
 except Exception as e:return jsonify(error='Email already registered or details missing'),400
 finally:c.close()
@app.route('/api/slots')
def slots():
 c=db(); rows=c.execute('''SELECT s.slot_id,s.slot_number,s.slot_type,s.status,f.floor_number,l.name lot_name FROM parking_slots s JOIN parking_floors f USING(floor_id) JOIN parking_lots l USING(lot_id) ORDER BY f.floor_number,s.slot_number''').fetchall(); c.close(); return jsonify([dict(x) for x in rows])
@app.route('/api/vehicles',methods=['GET','POST'])
def vehicles():
 c=db(); u=current(c)
 if not u:c.close(); return jsonify(error='Login required'),401
 if request.method=='POST':
  d=request.json or {}
  try:c.execute('INSERT INTO vehicles(user_id,registration_number,vehicle_type) VALUES(?,?,?)',(u['user_id'],d['registration'].upper(),d['type'])); c.commit()
  except Exception:c.close(); return jsonify(error='Registration number already exists'),400
 rows=c.execute('SELECT * FROM vehicles WHERE user_id=?',(u['user_id'],)).fetchall(); c.close(); return jsonify([dict(x) for x in rows])
@app.route('/api/reservations',methods=['GET','POST'])
def reservations():
 c=db(); u=current(c)
 if not u:c.close(); return jsonify(error='Login required'),401
 if request.method=='POST':
  d=request.json or {}; v=c.execute('SELECT * FROM vehicles WHERE vehicle_id=? AND user_id=?',(d.get('vehicle_id'),u['user_id'])).fetchone(); s=c.execute("SELECT * FROM parking_slots WHERE slot_id=? AND status='AVAILABLE'",(d.get('slot_id'),)).fetchone()
  if not v or not s:c.close(); return jsonify(error='Choose one of your vehicles and an available slot'),400
  now=datetime.now(); end=now+timedelta(hours=int(d.get('hours',2)))
  c.execute('INSERT INTO reservations(user_id,vehicle_id,slot_id,booking_time,start_time,end_time,status) VALUES(?,?,?,?,?,?,?)',(u['user_id'],v['vehicle_id'],s['slot_id'],now.isoformat(timespec='minutes'),now.isoformat(timespec='minutes'),end.isoformat(timespec='minutes'),'CONFIRMED'))
  c.execute("UPDATE parking_slots SET status='RESERVED' WHERE slot_id=?",(s['slot_id'],)); c.execute('INSERT INTO notifications(user_id,message,sent_at) VALUES(?,?,?)',(u['user_id'],f"Reservation confirmed for slot {s['slot_number']}.",now.isoformat(timespec='minutes'))); c.commit(); c.close(); return jsonify(ok=True)
 rows=c.execute('''SELECT r.*,s.slot_number,v.registration_number FROM reservations r JOIN parking_slots s USING(slot_id) JOIN vehicles v USING(vehicle_id) WHERE r.user_id=? ORDER BY r.reservation_id DESC''',(u['user_id'],)).fetchall(); c.close(); return jsonify([dict(x) for x in rows])
@app.route('/api/reservations/<int:rid>/cancel',methods=['POST'])
def cancel(rid):
 c=db(); u=current(c)
 if not u:c.close(); return jsonify(error='Login required'),401
 r=c.execute("SELECT * FROM reservations WHERE reservation_id=? AND user_id=? AND status='CONFIRMED'",(rid,u['user_id'])).fetchone()
 if not r:c.close(); return jsonify(error='Reservation cannot be cancelled'),400
 c.execute("UPDATE reservations SET status='CANCELLED' WHERE reservation_id=?",(rid,)); c.execute("UPDATE parking_slots SET status='AVAILABLE' WHERE slot_id=?",(r['slot_id'],)); c.commit(); c.close(); return jsonify(ok=True)
@app.route('/api/admin/overview')
def overview():
 c=db(); u=current(c)
 if not u or u['role']!='ADMIN':c.close(); return jsonify(error='Admin access required'),403
 data={'total':c.execute('SELECT COUNT(*) FROM parking_slots').fetchone()[0],'available':c.execute("SELECT COUNT(*) FROM parking_slots WHERE status='AVAILABLE'").fetchone()[0],'occupied':c.execute("SELECT COUNT(*) FROM parking_slots WHERE status='OCCUPIED'").fetchone()[0],'reserved':c.execute("SELECT COUNT(*) FROM parking_slots WHERE status='RESERVED'").fetchone()[0],'revenue':c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='SUCCESS'").fetchone()[0],'reservations':c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]}; c.close(); return jsonify(data)
@app.route('/api/admin/slots/<int:sid>',methods=['POST'])
def admin_slot(sid):
 c=db(); u=current(c); d=request.json or {}
 if not u or u['role']!='ADMIN':c.close(); return jsonify(error='Admin access required'),403
 if d.get('status') not in ['AVAILABLE','MAINTENANCE']:c.close(); return jsonify(error='Only AVAILABLE or MAINTENANCE can be set manually'),400
 c.execute('UPDATE parking_slots SET status=? WHERE slot_id=?',(d['status'],sid)); c.commit(); c.close(); return jsonify(ok=True)
@app.route('/api/admin/entry',methods=['POST'])
def entry():
 c=db(); u=current(c); d=request.json or {}
 if not u or u['role']!='ADMIN':c.close(); return jsonify(error='Admin access required'),403
 r=c.execute("SELECT * FROM reservations WHERE reservation_id=? AND status='CONFIRMED'",(d.get('reservation_id'),)).fetchone()
 if not r:c.close(); return jsonify(error='Confirmed reservation not found'),400
 now=datetime.now().isoformat(timespec='minutes'); c.execute('INSERT INTO sessions(reservation_id,vehicle_id,slot_id,entry_time) VALUES(?,?,?,?)',(r['reservation_id'],r['vehicle_id'],r['slot_id'],now)); c.execute("UPDATE parking_slots SET status='OCCUPIED' WHERE slot_id=?",(r['slot_id'],)); c.execute("UPDATE reservations SET status='COMPLETED' WHERE reservation_id=?",(r['reservation_id'],)); c.commit(); c.close(); return jsonify(ok=True)
@app.route('/api/admin/exit',methods=['POST'])
def exit_vehicle():
 c=db(); u=current(c); d=request.json or {}
 if not u or u['role']!='ADMIN':c.close(); return jsonify(error='Admin access required'),403
 s=c.execute("SELECT * FROM sessions WHERE session_id=? AND exit_time IS NULL",(d.get('session_id'),)).fetchone()
 if not s:c.close(); return jsonify(error='Active session not found'),400
 start=datetime.fromisoformat(s['entry_time']); end=datetime.now(); hours=max(1,(end-start).total_seconds()/3600); fee=round(hours*30,2)
 c.execute('UPDATE sessions SET exit_time=?,fee=? WHERE session_id=?',(end.isoformat(timespec='minutes'),fee,s['session_id'])); c.execute("UPDATE parking_slots SET status='AVAILABLE' WHERE slot_id=?",(s['slot_id'],)); c.execute('INSERT INTO payments(session_id,amount,payment_time,status) VALUES(?,?,?,?)',(s['session_id'],fee,end.isoformat(timespec='minutes'),'SUCCESS')); c.commit(); c.close(); return jsonify(ok=True,fee=fee)
@app.route('/api/admin/sessions')
def active_sessions():
 c=db(); u=current(c)
 if not u or u['role']!='ADMIN':c.close(); return jsonify(error='Admin access required'),403
 rows=c.execute("SELECT s.session_id,s.entry_time,v.registration_number,ps.slot_number FROM sessions s JOIN vehicles v USING(vehicle_id) JOIN parking_slots ps USING(slot_id) WHERE s.exit_time IS NULL").fetchall(); c.close(); return jsonify([dict(x) for x in rows])
@app.route('/api/notifications')
def notifications():
 c=db(); u=current(c)
 if not u:c.close(); return jsonify(error='Login required'),401
 rows=c.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY notification_id DESC LIMIT 20',(u['user_id'],)).fetchall(); c.close(); return jsonify([dict(x) for x in rows])

init_db()
if __name__=='__main__': app.run(debug=True)
