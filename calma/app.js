// CALMA — prototipe frontend (mengikuti desain Figma)
const $=id=>document.getElementById(id);
const API_BASE = (window.location.origin || 'http://127.0.0.1:8000');
const api = async (path, options = {}) => {
  const headers = options.headers ? {...options.headers} : {};
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  if (S.token) headers.Authorization = `Bearer ${S.token}`;
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const detail = payload.detail;
    const message = Array.isArray(detail)
      ? detail.map(issue => {
          const field = Array.isArray(issue.loc) ? issue.loc.at(-1) : '';
          if (field === 'password' && issue.type === 'string_too_short') return 'Kata sandi minimal 12 karakter.';
          return issue.msg || 'Data yang dikirim tidak valid.';
        }).join(' ')
      : typeof detail === 'string' ? detail : 'Request gagal. Periksa kembali data yang dimasukkan.';
    throw new Error(message);
  }
  return payload;
};
const P={home:'M3 11l9-8 9 8M5 10v10h14V10M10 20v-6h4v6',quest:'M12 21a9 9 0 100-18 9 9 0 000 18zM12 16a4 4 0 100-8 4 4 0 000 8z',chat:'M4 5h16v11H9l-5 4z',ticket:'M4 7h16v3a2 2 0 000 4v3H4v-3a2 2 0 000-4z',user:'M12 12a4 4 0 100-8 4 4 0 000 8zM4 21c0-4 4-6 8-6s8 2 8 6',bell:'M6 16v-5a6 6 0 0112 0v5l2 2H4zM10 21h4',shield:'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z',phone:'M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A15 15 0 013 6a2 2 0 012-2z',cal:'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4',x:'M6 6l12 12M18 6L6 18',check:'M5 12l5 5 9-10',pulse:'M3 12h4l2-6 4 12 2-6h6',send:'M4 12l16-8-6 16-3-7z',
Tenang:'M12 21a9 9 0 100-18 9 9 0 000 18zM8.5 14c1 1.5 2.200 2 3.5 2s2.500-.5 3.500-2M9 9.500v.5M15 9.500v.5',Lelah:'M12 21a9 9 0 100-18 9 9 0 000 18zM8.500 15h7M9 9.500v.5M15 9.500v.5',Sedih:'M12 21a9 9 0 100-18 9 9 0 000 18zM8.500 16c1-1.500 2.200-2 3.500-2s2.500.5 3.500 2M9 9.500v.5M15 9.500v.5',Penuh:'M7 18a4 4 0 01-.5-8 5.500 5.500 0 0110.500 1A3.500 3.500 0 0117 18z',Berenergi:'M13 3L5 14h6l-1 7 8-11h-6z'};
const ic=(n,s=20)=>`<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${P[n]}"/></svg>`;
const S={user:{name:'Nadya',email:'nadya@email.com'},contact:{name:'Celsi',tel:'082361771234'},hist:[],cur:null,voucher:false,mood:'Sedih',alert:'A',tele:{},cd:null,
 perms:{watch:1,mood:1,contact:1,pro:0,chat_external:0},chat:[],token:null};
const week=[['Sen','Senin','Tenang',76],['Sel','Selasa','Lelah',81],['Rab','Rabu','Tenang',79],['Kam','Kamis','Penuh',86],['Jum','Jumat','Lelah',91],['Sab','Sabtu','Sedih',94],['Min','Minggu','Penuh',89]];
const hari=['Minggu','Senin','Selasa','Rabu','Kamis','Jumat','Sabtu'],bln=['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'];
const days=()=>[1,2,3].map(i=>{const d=new Date();d.setDate(d.getDate()+i);return (i==1?'Besok · ':'')+hari[d.getDay()]+', '+d.getDate()+' '+bln[d.getMonth()]});
const lvl=b=>b>=88?'Tinggi':b>=80?'Sedang':'Rendah';
const img=(n,c='hero',w='')=>`<img class="${c}" src="img/${n}.png" alt="" ${w}>`;
const btn=(t,go,c='')=>`<button class="btn ${c}" data-go="${go}">${t}</button>`;
const back=(to,t='Kembali')=>`<button class="back" data-back="${to||''}">‹ ${t}</button>`;
const head=(k,t,s,c='')=>`<div class="col ${c}"><div class="kick">${k}</div><h1>${t}</h1>${s?`<p>${s}</p>`:''}</div>`;
const tile=(i,c='')=>`<span class="tile ${c}">${ic(i,22)}</span>`;
const greet=()=>{const h=new Date().getHours();return h<11?'pagi':h<15?'siang':h<18?'sore':'malam'};

const QUEST_DURATION_SECONDS = 10 * 60;
const formatCountdown = totalSeconds => {
  const safeSeconds = Math.max(0, totalSeconds);
  const minutes = Math.floor(safeSeconds / 60);
  const seconds = safeSeconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
};

const onb=(i,im,k,t,s,next,last)=>`<div class="brand">CALMA</div><div class="dots">${[0,1,2].map(n=>`<i class="${n==i?'on':''}"></i>`).join('')}</div>
 <div class="grow" style="display:grid;place-items:center">${img(im,'hero','style="max-height:300px"')}</div>
 ${head(k,t,s,'c')}<div style="height:6px"></div>${btn(last?'Mulai dengan aman':'Lanjut',next)}${last?'':btn('Lewati pengenalan','login','ghost')}`;
const auth=su=>`<div class="brand">CALMA</div><div class="c col">${img(su?'calm':'wink','hero','style="height:150px"')}</div>
 ${head(su?'Ruang tenangmu':'Selamat datang kembali',su?'Kenali sinyal tubuh, redam bersama.':'Pelan-pelan, kita mulai lagi.',su?'Pendamping pribadi yang belajar memahami ritme tubuhmu, tanpa menghakimi.':'Masuk untuk melanjutkan perjalananmu bersama CALMA.','c')}
 <div class="seg"><button data-go="login" class="${su?'':'on'}">Masuk</button><button data-go="signup" class="${su?'on':''}">Daftar</button></div>
 ${su?'<label>Nama panggilan<input type="text" id="f-name" placeholder="Kamu ingin dipanggil apa?"></label>':''}
 <label>Email<input type="email" id="f-mail" placeholder="Masukkan email kamu"></label><label>Kata sandi<input type="password" id="f-pw" placeholder="Minimal 12 karakter"></label>
 <div class="err" id="err"></div>${su?'':'<button class="link" style="align-self:flex-end">Lupa kata sandi?</button>'}
 <button class="btn" id="auth-go">${su?'Buat akun dengan aman':'Masuk ke CALMA'}</button><p class="small c">Dengan melanjutkan, kamu menyetujui Ketentuan dan Kebijakan Privasi CALMA.</p>`;

const alertCard=()=>{const a=S.alert,B=(t,k,c='')=>`<button class="btn ${c}" data-al="${k}">${t}</button>`,hd='<div class="kick" style="letter-spacing:.06em">CALMA AI · SINYAL MENINGKAT</div>';
 const m={A:`${hd}<h2 class="t">Nadya, kamu sepertinya lagi banyak pikiran.</h2><p class="t">Detak jantungmu di atas baseline. Benar lagi stres?</p>${B('Iya, aku lagi stres','yes')}${B('Nggak kok, aku aman','no','soft')}<p class="small c">Kita cek bareng, ya?</p>`,
 B:`${hd}<h2 class="t">Pastikan sekali lagi, ya.</h2><p class="t">Perubahan ritmemu masih cukup tinggi. Mau cek singkat bareng CALMA sebelum menutup peringatan?</p>${B('Yuk, cek bareng','yes')}${B('Aku yakin sedang aman','sure','soft')}`,
 C:`${hd}<h2 class="t">Baik, terima kasih sudah mengonfirmasi.</h2><p class="t">CALMA tetap memantau dengan tenang. Kamu bisa cek bareng kapan saja jika berubah pikiran.</p>${B('Cek bareng KALMI!','yes','soft')}`,
 D:`<div class="kick" style="color:#557bc1">TERIMA KASIH SUDAH JUJUR</div><h2 class="t">Aku di sini. Kita nggak perlu buru-buru.</h2><p class="t">Kamu punya cukup energi untuk satu langkah kecil?</p>${B('Pilih quest paling ringan','quest')}${B('Aku cuma mau didengar','listen','soft')}`}[a];
 return `<div class="card alert" id="alert">${img(a=='D'?'hug':'alert','','alt=""')}${m}</div>`};

const rows=r=>r.map(x=>`<div class="row" style="padding:10px 0;border-top:1px solid #eef2f9"><p>${x[0]}</p><b style="font-size:12px;text-align:right">${x[1]}</b></div>`).join('');
const step=(n,t,s,go)=>`<div class="li" data-go="${go}"><span class="num">${n}</span><div class="grow"><h2>${t}</h2><p style="font-size:11px">${s}</p></div><span style="color:#aaa3b1">›</span></div>`;
const done=(k,t,s,cta,to,i='check')=>`${back('safe','Rencana aman')}<div class="grow"></div><div class="col c">${tile(i,'k')}</div>${head(k,t,'','c')}<div class="card"><p class="c">${s}</p>${btn(cta,to)}</div><div class="grow"></div>`;
const sub=(i,k,t,s,c='')=>`<div class="col c" style="margin-top:20px">${tile(i,c)}</div>${head(k,t,s,'c')}`;

const screens={
 s1:()=>onb(0,'wave','Kenali polamu','Tubuhmu punya cerita.','CALMA membaca perubahan ritme tubuh dan suasana hati untuk mengenali stres lebih awal.','s2'),
 s2:()=>onb(1,'dance','Dukungan yang sesuai','Langkah kecil, sesuai energimu.','Quest dipilih otomatis dari data dan check-in harianmu.','s3'),
 s3:()=>onb(2,'heart','Kamu tetap memegang kendali','Privasi dan keselamatan lebih dulu.','Setiap jenis data membutuhkan izinmu. Dalam situasi krisis, CALMA menampilkan safety plan dan akses 119.','signup',1),
 login:()=>auth(0),signup:()=>auth(1),
 home:()=>{const d=new Date().toLocaleDateString('id-ID',{weekday:'long',day:'numeric',month:'long'}).toUpperCase();
  return `<div class="row"><span class="brand">CALMA</span><div class="row" style="gap:8px"><button class="tile hb" data-go="voucher" aria-label="Voucher Saya">${ic('ticket',16)}${S.voucher?'<i class="bdg">1</i>':''}</button><button class="tile g hb" style="font-weight:800" data-go="profile" aria-label="Profil">${S.user.name[0]}</button></div></div>
  <div style="position:relative;padding-right:90px"><div class="kick" style="color:#4778d5">${d}</div><h1 style="font-size:24px;margin:4px 0">Selamat ${greet()}, ${S.user.name}.</h1><p>Bagaimana kabar tubuh dan pikiranmu hari ini?</p>${img('peek','','style="position:absolute;right:-6px;top:-4px;width:78px"')}</div>
  <div class="row" style="align-items:stretch"><div class="card mini" data-modal="mood"><div class="row l">${tile('Tenang','')}<div class="tt"><h2>Cek suasana hati ›</h2><p>${S.moodSet?'Hari ini: '+S.mood:'Ceritakan Perasaanmu'}</p></div></div></div>
  <div class="card mini"><div class="row l">${tile('pulse','g')}<div class="tt"><h2><span class="dot on" style="margin-right:5px"></span>Apple Watch S9</h2><p>Terhubung 2 menit lalu</p></div></div></div></div>
  <div class="card blue"><div class="row l">${tile('pulse','g')}<div class="grow"><h2>Ritme tubuhmu terpantau</h2></div><span class="pill">LANGSUNG</span></div><p>CALMA membandingkan detak saat ini dengan pola baseline pribadimu.</p>
   <div class="wave">${Array.from({length:36},(_,i)=>`<i style="height:${8+Math.abs(Math.sin(i*1.3))*20|0}px;animation-delay:${i*50}ms"></i>`).join('')}</div>
   <div class="row"><span class="small" style="color:#536a94;font-weight:700"><span class="dot"></span>Data stabil</span><button class="link" data-modal="detail">Detail ritme ›</button></div></div>
  <div class="card"><div class="row"><div><div class="kick">Rekap 7 hari</div><h2>Pola stres harian</h2></div><span class="pill w">3 hari tinggi</span></div>
   <div class="bars">${week.map(w=>`<div><span><b class="${w[3]>=88?'hi':''}" style="height:${(w[3]-60)*2.6}%"></b></span>${w[0]}</div>`).join('')}</div>
   <div class="row" style="gap:8px"><div class="stat"><p>Rata-rata detak jantung</p><b>84 bpm</b></div><div class="stat"><p>Waktu tenang</p><b>4j 20m</b></div></div><button class="link" style="align-self:flex-end" data-go="rincian">Lihat rincian harian ›</button></div>
  <div class="card peach"><h2>Stres tinggi terpantau 3 hari</h2><p>Kalau kamu berkenan, CALMA dapat membantu menjadwalkan telekonsultasi.</p><button class="btn peach" data-go="tele">Atur telekonsultasi</button></div>
  ${alertCard()}<p class="small c">CALMA bukan alat diagnosis medis. AI hanya membantu mengenali perubahan pola pribadimu.</p>`},
 rincian:()=>`${back('home')}${head('Rekap 7 hari','Rincian pola harian','Data contoh dari jam tangan dan catatan suasana hati.')}
  <div class="card" style="padding:6px 16px">${week.map(w=>`<div class="li"><div class="grow"><h2>${w[1]}</h2><p style="font-size:11px">${w[2]}</p></div><div style="text-align:right"><h2>${w[3]} bpm</h2><p style="font-size:11px;font-weight:700;${w[3]>=88?'color:#b65f64':''}">${lvl(w[3])}</p></div></div>`).join('')}</div>`,
 quest:()=>`${back('home')}<div class="row"><div class="kick">Quest adaptif</div><span class="pill">Energi rendah</span></div><h1>Sesuai energimu hari ini.</h1>
  <div class="card"><div style="background:linear-gradient(#bfe7f8,#e8f5fd);border-radius:18px;padding:10px;text-align:center">${img('quest','','style="height:130px"')}</div><div class="kick" style="margin-top:6px">Dipilih otomatis dari datamu</div><h1 style="font-size:22px">Jalan pelan 10 menit</h1><p>Nggak perlu jauh. Bergerak pelan sambil memperhatikan napas sudah cukup.</p>
  <div class="chips">${['Ringan','10 menit','Voucher otomatis'].map(t=>`<span class="pill" style="background:#f4f6fb;color:#716a7c">${t}</span>`).join('')}</div>${btn('Mulai quest','run')}</div>
  <div class="card warm"><p style="color:#57746e;font-weight:600">Tingkat ringan dipilih otomatis. Rekomendasi memakai data ritme tubuh dan check-in suasana hati “${S.mood}”.</p></div>`,
 run:()=>`${back('quest')}<div class="card" style="gap:12px"><div class="row"><div><div class="big" style="font-size:28px" id="clock">${formatCountdown(QUEST_DURATION_SECONDS)}</div><p style="font-size:11px">dari 10 menit</p></div><span class="pill"><span class="dot"></span>AKTIVITAS TERBACA</span></div><div class="prog"><i id="pg"></i></div>
  <h1 style="font-size:22px">Ritmemu terlihat konsisten.</h1><p>Detak jantung bergerak wajar selama aktivitas. Teruskan dengan nyaman, ya.</p>
  <div class="sub"><div class="row"><h2>Detak saat ini</h2><b style="color:var(--acc)"><span id="bpm">102</span> bpm</b></div></div><button class="btn" id="finish" disabled>Selesaikan dan terima voucher</button><p class="small c" id="hint">Selesaikan 10 menit dulu untuk membuka tombol ini.</p>${btn('Berhenti tanpa penalti','quest','ghost')}</div>`,
 reward:()=>{S.voucher=true;return `<div class="row"><div class="kick">Hadiah pemulihan</div><p class="small">1 dari 3 minggu ini</p></div><div class="c col">${img('medal','hero','style="height:200px"')}</div>${head('','Satu langkah kecilmu berarti.','Hadiah langsung diberikan berdasarkan quest yang selesai, tanpa perlu memilih.','c').replace('<div class="kick"></div>','')}
  <div class="card"><div class="row l">${tile('food','g').replace(/<svg.*<\/svg>/,'<img src="img/food.png">')}<div><div class="kick" style="font-size:9px">GoFood · otomatis tersimpan</div><h2>Diskon Rp25.000</h2><p style="font-size:11px;line-height:1.3">Min. pembelian Rp50.000</p></div></div><div class="pill g c" style="padding:11px;border-radius:12px">Tersimpan</div></div>
  <p class="small c">Hadiah adalah bonus, bukan ukuran keberhasilanmu.</p>${btn('Kembali ke beranda','home')}`},
 voucher:()=>S.voucher?`${head('Hadiah tersimpan','Voucher Saya','Voucher quest-mu tersimpan aman di perangkat ini.')}
  <div class="card"><div class="row l">${tile('x','g').replace(/<svg.*<\/svg>/,'<img src="img/food.png">')}<div><div class="kick" style="font-size:9px">GoFood</div><h2>Diskon Rp25.000</h2><p style="font-size:11px;line-height:1.3">Min. pembelian Rp50.000</p></div></div>
  <div class="sub row"><span class="small" style="font-weight:800;letter-spacing:.08em">KODE VOUCHER</span><b style="color:#426fc8">CALMA25K</b></div><button class="btn" onclick="navigator.clipboard&&navigator.clipboard.writeText('CALMA25K');this.textContent='Tersalin ✓'">Pakai di GoFood</button></div><p class="small c">Nantinya status penggunaan akan tersinkron otomatis setelah integrasi mitra aktif.</p>`
  :`${head('Hadiah tersimpan','Voucher Saya','Voucher quest-mu tersimpan aman di perangkat ini.')}<div class="card c"><h2 style="font-size:16px;margin-top:10px">Belum ada voucher</h2><p>Selesaikan quest untuk mendapatkan hadiah pemulihan pertamamu.</p>${btn('Lihat quest','quest')}</div><p class="small c">Nantinya status penggunaan akan tersinkron otomatis setelah integrasi mitra aktif.</p>`,
 chat:()=>`<div class="row l" style="gap:10px"><img src="img/wave.png" style="width:42px;height:42px;object-fit:cover;object-position:top;border-radius:50%;background:#e6efff"><div class="grow"><div class="kick" style="font-size:10px">Teman AI · hadir</div><h1 style="font-size:20px">Calmi</h1></div><b style="color:#8c8596">•••</b></div>
  <p class="small c" style="font-weight:700;letter-spacing:.1em">HARI INI</p><div class="chat" id="chat"></div>
  <div class="inp"><input type="text" id="msg" placeholder="Tulis apa yang kamu rasakan..."><button class="send" id="send">${ic('send',16)}</button></div>`,
 safe:()=>`${back('')}${head('Ruang amanmu','Rencana aman','Langkah yang sudah kamu pilih sendiri untuk saat semuanya terasa terlalu berat.')}
  <div class="card blue"><div class="row l">${tile('shield')}<div><h2>Kamu tetap pegang kendali</h2><p style="font-size:11px;line-height:1.5">Tidak ada kontak yang dihubungi tanpa persetujuan atau hitung mundur yang bisa kamu batalkan.</p></div></div></div>
  <div class="card" style="padding:4px 16px">${step(1,'Tenangkan tubuh','Duduk di tempat terang','calm')}${step(2,'Hubungi orang aman',`${S.contact.name} · ${S.contact.tel}`,'contact')}${step(3,'Cari bantuan profesional','Telekonsultasi dan layanan darurat 119','pro')}</div>
  <div id="cdbox">${S.cd?cdCard():'<button class="btn peach" id="need">Aku butuh ditemani sekarang</button>'}</div><p class="small c">Kontak terakhir: belum ada · Batas 1 ping / 24 jam</p>`,
 calm:()=>`${back('safe','Rencana aman')}${sub('shield','Tenangkan tubuh','Ikuti perlahan, satu per satu.','p')}<div class="card">${['Duduk di tempat yang terasa aman dan terang.','Letakkan kedua kaki di lantai dan rasakan pijakannya.','Tarik napas 4 hitungan, tahan 2, keluarkan 6 hitungan.','Sebutkan 3 benda yang bisa kamu lihat di sekitarmu.'].map((t,i)=>`<div class="sub row l" style="padding:11px"><span class="num">${i+1}</span><h2 style="font-size:12px">${t}</h2></div>`).join('')}${btn('Aku sudah lebih tenang','home')}${btn('Aku belum tenang','safe','ghost')}</div>`,
 contact:()=>`${back('safe','Rencana aman')}${sub('phone','Hubungi orang aman',`Kirim pesan kepada ${S.contact.name}?`,'','p')}<div class="card"><div class="sub row l"><span class="tile g" style="width:36px;height:36px;border-radius:12px;font-weight:800">${S.contact.name[0]}</span><div><h2>${S.contact.name}</h2><p style="font-size:11px">${S.contact.tel}</p></div></div><p>Pesan yang dikirim: “Aku sedang butuh ditemani. Bisa hubungi aku?” Data kesehatan tidak ikut dibagikan.</p>${btn('Ya, kirim pesan','contactOk')}</div>`,
 contactOk:()=>done('Konfirmasi berhasil',`Pesan siap dikirim ke ${S.contact.name}.`,'Dalam versi terhubung, status pengiriman akan ditampilkan di sini.','Kembali ke rencana aman','safe'),
 pro:()=>`${back('safe','Rencana aman')}${sub('phone','Bantuan profesional','Hubungi layanan kesehatan?','','p')}<div class="card"><div class="card peach c"><p>Layanan darurat kesehatan</p><div class="big" style="color:#7a5358">119</div><p>Tersedia 24 jam</p></div><p>Panggilan hanya dilakukan setelah kamu menekan tombol konfirmasi di bawah.</p>${btn('Konfirmasi hubungi 119','callOk','danger')}${btn('Atur telekonsultasi saja','tele','soft')}</div>`,
 callOk:()=>done('Konfirmasi berhasil','Panggilan ke 119 siap dilakukan.','Dalam versi terhubung, perangkat akan membuka panggilan telepon.','Kembali ke rencana aman','safe')+'<a href="tel:119" class="link c" style="text-align:center">Buka telepon 119</a>',
 tele:()=>{S.tele={};return `${back('')}${sub('cal','Telekonsultasi','Pilih waktu yang nyaman.','','p')}<div class="card"><label>Tanggal konsultasi</label><div class="chips" data-pick="date">${days().map(d=>`<button class="chip" style="width:100%;text-align:left">${d}</button>`).join('')}</div><label>Waktu konsultasi</label><div class="chips" data-pick="time">${['09.00','13.00','16.00','19.30'].map(d=>`<button class="chip">${d}</button>`).join('')}</div><button class="btn" id="tele-ok" disabled>Konfirmasi jadwal</button><p class="small c" id="err">Pilih tanggal dan waktu untuk melanjutkan.</p></div><p class="small c">Tenaga profesional hanya melihat informasi yang kamu setujui. Catatan percakapan AI tidak ikut dibagikan.</p>`},
 teleOk:()=>`<div class="grow"></div><div class="col c">${tile('check','k')}</div>${head('Jadwal tersimpan','Telekonsultasi berhasil diatur.','','c')}<div class="card"><p class="c">Jadwal ${S.tele.date} pukul ${S.tele.time} telah disimpan. Pengingat akan muncul sebelum sesi dimulai.</p>${btn('Kembali ke beranda','home')}</div><div class="grow"></div>`,
 profile:()=>`${back('')}${head('Akun dan preferensi','Pengaturan')}
  <div class="card c"><span class="tile g" style="width:56px;height:56px;font-weight:800;font-size:20px">${S.user.name[0]}</span><h2 style="font-size:17px">${S.user.name}</h2><p style="font-size:11px">Profil pribadi terverifikasi</p></div>
  <div class="card"><h2>Profil</h2>${rows([['Nama panggilan',S.user.name],['Email',S.user.email],['Nomor telepon','0812 3456 7890'],['Tanggal lahir','14 Mei 1998']])}</div>
  <div class="card"><h2>Kontak darurat</h2>${rows([['Nama kontak',S.contact.name],['Nomor kontak',S.contact.tel]])}</div>
  <div class="card"><h2>Privasi dan izin data</h2><p>Izin jam tangan, suasana hati, kontak darurat, dan layanan profesional dapat ditinjau satu per satu.</p><button class="btn soft" data-go="consent" style="color:#4f73b7;width:auto;align-self:flex-start;padding:10px 14px">Kelola izin data</button></div>
  ${btn('Buka rencana aman','safe','soft')}${btn('Keluar','login','ghost')}`,
 consent:()=>`${back('profile','Pengaturan')}${sub('shield','Privasi','Kelola izin data','Aktifkan hanya data yang boleh digunakan CALMA.')}<div class="card"><div style="padding:0 2px">${[['watch','Data jam tangan','Detak jantung, tidur, dan aktivitas'],['mood','Suasana hati','Catatan harian'],['contact','Kontak darurat','Digunakan setelah konfirmasi'],['pro','Layanan profesional','Tawaran telekonsultasi'],['chat_external','Pemrosesan chat AI eksternal','Pesan dan maksimal 12 giliran chat dikirim ke provider pilihanmu']].map(p=>`<div class="li" style="cursor:default"><div class="grow"><h2>${p[1]}</h2><p style="font-size:11px">${p[2]}</p></div><input type="checkbox" class="sw" data-perm="${p[0]}" ${S.perms[p[0]]?'checked':''}></div>`).join('')}</div><p class="small" id="chat-consent-status">Consent chat eksternal hanya berlaku untuk percakapan dan dapat dicabut kapan saja.</p>${btn('Simpan izin','profile')}</div>`
};
const auths=['s1','s2','s3','login','signup'];
const tabs=[['home','home'],['quest','quest'],['chat','chat'],['safe','shield'],['profile','user']];
const tabOf={home:'home',rincian:'home',quest:'quest',run:'quest',reward:'quest',chat:'chat',safe:'safe',calm:'safe',contact:'safe',contactOk:'safe',pro:'safe',callOk:'safe',profile:'profile',consent:'profile'};
function cdCard(){const s=S.cd.left;return `<div class="card peach c"><p style="font-weight:700">Pesan netral akan dikirim ke ${S.contact.name} dalam</p><div class="big" id="cd" style="color:#3f3a4a">${String(s/60|0).padStart(2,'0')}:${String(s%60).padStart(2,'0')}</div><p style="font-size:11px">“Aku lagi butuh ditemani. Bisa hubungi aku?” Tidak ada data kesehatan yang dibagikan.</p><button class="btn soft" id="cancel" style="width:auto;padding:10px 16px">Batalkan pengiriman</button></div>`}
function go(id,push=true){if(push&&S.cur&&S.cur!=id)S.hist.push(S.cur);S.cur=id;clearInterval(S.t);$('modal').hidden=true;
 $('screen').innerHTML=screens[id]();$('screen').scrollTop=0;const n=$('nav');n.hidden=auths.includes(id);
 n.innerHTML=tabs.map(t=>`<button class="${tabOf[id]==t[0]?'on':''}" data-go="${t[0]}" aria-label="${t[0]}">${ic(t[1],22)}</button>`).join('');after(id)}
function after(id){
 if(id=='run'){
  let elapsed = 0;
  const updateQuestTimer = () => {
   elapsed = Math.min(QUEST_DURATION_SECONDS, elapsed + 1);
   const remaining = QUEST_DURATION_SECONDS - elapsed;
   const clock = $('clock');
   const progress = $('pg');
   if (clock) clock.textContent = formatCountdown(remaining);
   if (progress) progress.style.width = `${(elapsed / QUEST_DURATION_SECONDS) * 100}%`;
   const bpm = $('bpm'); if (bpm) bpm.textContent = 100 + (Math.random() * 6 | 0);
   if (elapsed >= QUEST_DURATION_SECONDS) {
    clearInterval(S.t);
    const finish = $('finish'); if (finish) finish.disabled = false;
    const hint = $('hint'); if (hint) hint.textContent = 'Quest selesai. Ritmemu konsisten sepanjang aktivitas.';
   }
  };
  updateQuestTimer();
  S.t = setInterval(updateQuestTimer, 1000);
 }
 if(id=='chat'){if(!S.chat.length)S.chat=[['ai','Hai, '+S.user.name+'. Kamu bisa cerita tentang situasimu atau bantuan yang sedang kamu cari.']];drawChat()}
 if(id==='consent')api('/api/v1/consents').then(consents=>{
  const status=consents.find(item=>item.purpose==='external_chat_processing');
  S.perms.chat_external=Boolean(status&&status.granted);
  const control=document.querySelector('[data-perm="chat_external"]');
  if(control)control.checked=S.perms.chat_external;
 }).catch(error=>{const status=$('chat-consent-status');if(status)status.textContent='Status consent belum dapat dimuat: '+error.message});
 if(id=='safe'&&S.cd)tick()}
function tick(){clearInterval(S.t);S.t=setInterval(()=>{if(!S.cd)return;S.cd.left--;if(S.cur!='safe')return;if(S.cd.left<=0){S.cd=null;return go('contactOk')}$('cd')&&($('cd').textContent=String(S.cd.left/60|0).padStart(2,'0')+':'+String(S.cd.left%60).padStart(2,'0'))},1000)}
function toast(){const t=$('toast');t.innerHTML=`<span class="tile g">${ic('ticket',22)}</span><div><h2 style="font-size:12px">Voucher GOFOOD berhasil didapatkan!</h2><p style="font-size:11px;line-height:1.45">Voucher sudah masuk ke Voucher Saya dan siap digunakan.</p></div>`;t.classList.add('show');clearTimeout(S.tt);S.tt=setTimeout(()=>t.classList.remove('show'),4500)}
function drawChat(){
 const c=$('chat');c.replaceChildren();
 S.chat.forEach(([role,text])=>{const bubble=document.createElement('div');bubble.className=`bub ${role}`;bubble.textContent=text;c.append(bubble)});
 if(S.chat.length<6){['Aku cuma mau didengar','Ajak aku melakukan hal yang produktif','Bantu pilih quest ringan'].forEach(text=>{const reply=document.createElement('button');reply.className='qr';reply.textContent=text;c.append(reply)})}
 $('screen').scrollTop=1e5
}
async function say(value){
 S.chat.push(['me',value]);drawChat();
 const history=S.chat.slice(0,-1).slice(-12).map(([role,content])=>({role:role==='me'?'user':'assistant',content}));
 const send=$('send');if(send)send.disabled=true;
 try{
  const response=await api('/api/v1/chatbot/messages',{method:'POST',body:JSON.stringify({
  message:value,history,request_quest:/quest|aktivitas|jalan|olahraga/i.test(value),energy:'low'
  })});
  S.chat.push(['ai',response.text]);
 }catch(error){S.chat.push(['ai','Maaf, pesan belum terkirim. '+(error.message||'Coba masuk kembali lalu ulangi.')])}
 if(S.cur==='chat')drawChat();
 const currentSend=$('send');if(currentSend)currentSend.disabled=false;
}
function modal(t){const m=$('modal');m.hidden=false;
 m.innerHTML=t=='mood'?`<div class="sheet"><div class="row" style="align-items:flex-start"><div><div class="kick">Check-in harian</div><h1 style="font-size:22px;margin-top:4px">Apa yang paling mendekati perasaanmu?</h1><p>Pilih satu yang terasa paling sesuai saat ini.</p></div><button class="xbtn" data-close>${ic('x',16)}</button></div>
  <div class="moods">${['Tenang','Lelah','Sedih','Penuh','Berenergi'].map(x=>`<button data-mood="${x}" class="${S.moodSet&&S.mood==x?'on':''}"><span class="tile">${ic(x,22)}</span>${x}</button>`).join('')}</div><p class="small c">Check-in ini hanya dipakai untuk menyesuaikan rekomendasi harianmu.</p></div>`
 :`<div class="sheet"><div class="row" style="align-items:flex-start"><div class="row l">${tile('pulse','g')}<div><div class="kick">Detail ritme</div><h1 style="font-size:22px">Data tubuh hari ini</h1></div></div><button class="xbtn" data-close>${ic('x',16)}</button></div><p>Ringkasan dibandingkan dengan baseline pribadimu selama delapan hari.</p>
  <div class="row" style="gap:8px">${[['Detak saat ini','92 bpm','+8 dari baseline'],['Rata-rata istirahat','78 bpm','Stabil']].map(s=>`<div class="stat"><p>${s[0]}</p><b>${s[1]}</b><em>${s[2]}</em></div>`).join('')}</div>
  <div class="row" style="gap:8px">${[['Durasi tidur','6j 42m','-38 menit'],['Variabilitas detak','41 ms','Sedikit turun']].map(s=>`<div class="stat"><p>${s[0]}</p><b>${s[1]}</b><em>${s[2]}</em></div>`).join('')}</div>
  <div class="sub" style="background:#eef4ff"><p style="color:#5570a2;font-weight:600">Tegangan meningkat selama 18 menit terakhir, tetapi belum menunjukkan keadaan darurat.</p></div><button class="btn" data-close>Mengerti</button></div>`}
document.addEventListener('click',e=>{const t=e.target.closest('[data-go],[data-back],[data-modal],[data-close],[data-mood],[data-al],[data-perm],.chip,.qr,#auth-go,#tele-ok,#finish,#send,#need,#cancel');if(!t)return;const d=t.dataset;
 if(d.go)go(d.go);
 else if(t.hasAttribute('data-back'))d.back?go(d.back):go(S.hist.pop()||'home',false);
 else if(d.modal)modal(d.modal);
 else if('close' in d)$('modal').hidden=true;
 else if(d.mood){S.mood=d.mood;S.moodSet=1;t.parentNode.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b==t));
  (async () => {
    try {
      const moodMap = { Tenang: 'good', Lelah: 'low', Sedih: 'low', Penuh: 'good', Berenergi: 'good' };
      const energyMap = { Tenang: 'medium', Lelah: 'low', Sedih: 'low', Penuh: 'high', Berenergi: 'high' };
      await api('/api/v1/mood-checkins', {
        method: 'POST',
        body: JSON.stringify({ mood: moodMap[S.mood] || 'low', energy: energyMap[S.mood] || 'medium' })
      });
    } catch (error) {
      console.warn('Mood sync failed:', error);
    }
    setTimeout(()=>{$('modal').hidden=true;if(S.cur=='home')go('home',false)},450);
  })();
 }
 else if(d.al){const a=d.al;if(a=='quest')return go('quest');if(a=='listen'){S.chat=[];return go('chat')}S.alert={yes:'D',no:'B',sure:'C'}[a];$('alert').outerHTML=alertCard()}
 else if(t.classList.contains('qr'))say(t.textContent);
 else if(t.classList.contains('chip')){t.parentNode.querySelectorAll('.chip').forEach(c=>c.classList.remove('on'));t.classList.add('on');S.tele[t.parentNode.dataset.pick]=t.textContent;const b=$('tele-ok');if(b){const ok=S.tele.date&&S.tele.time;b.disabled=!ok;$('err').textContent=ok?'':'Pilih tanggal dan waktu untuk melanjutkan.'}}
 else if(t.id=='auth-go'){const mail=$('f-mail').value.trim(),pw=$('f-pw').value,nm=$('f-name');
  if(!/\S+@\S+\.\S+/.test(mail))return $('err').textContent='Masukkan email yang valid.';
  if(pw.length<12)return $('err').textContent='Kata sandi minimal 12 karakter.';
  S.user.email=mail;S.user.name=nm&&nm.value.trim()||mail.split('@')[0].replace(/^./,c=>c.toUpperCase());
  const mode = S.cur === 'signup' ? 'register' : 'login';
  const payload = { email: mail, password: pw };
  (async () => {
    try {
      if (mode === 'register') {
        await api('/api/v1/auth/register', { method: 'POST', body: JSON.stringify(payload) });
      }
      const login = await api('/api/v1/auth/login', { method: 'POST', body: JSON.stringify(payload) });
      S.token = login.access_token;
      S.hist=[];S.cur=null;go('home');
    } catch (error) {
      $('err').textContent = error.message || 'Login gagal';
    }
  })();
 }
 else if(t.id=='finish'){go('reward');toast()}
 else if(t.id=='tele-ok'){if(!S.tele.date||!S.tele.time)return $('err').textContent='Pilih tanggal dan waktu dulu, ya.';go('teleOk')}
 else if(t.id=='send'){const i=$('msg'),v=i.value.trim();if(v){i.value='';say(v)}}
 else if(t.id=='need'){S.cd={left:600};$('cdbox').innerHTML=cdCard();tick()}
 else if(t.id=='cancel'){S.cd=null;clearInterval(S.t);$('cdbox').innerHTML='<button class="btn peach" id="need">Aku butuh ditemani sekarang</button>'}
 else if(d.perm==='chat_external'){
  const granted=t.checked;t.disabled=true;
  api('/api/v1/consents/external_chat_processing',{method:'PUT',body:JSON.stringify({granted})})
   .then(()=>{S.perms.chat_external=granted})
   .catch(error=>{t.checked=!granted;const status=$('chat-consent-status');if(status)status.textContent='Consent gagal diperbarui: '+error.message})
   .finally(()=>{t.disabled=false});
 }
 else if(d.perm)S.perms[d.perm]=t.checked});
document.addEventListener('keydown',e=>{if(e.key=='Enter'&&e.target.id=='msg')$('send').click()});
go('s1');
