import json

def generate_master_report(json_filepath):
    # 1. Load the Master Database
    print(f"Loading database from {json_filepath}...")
    try:
        with open(json_filepath, 'r') as f:
            db = json.load(f)
    except FileNotFoundError:
        print("Error: Could not find JSON database.")
        return

    gene_677 = db.get('MTHFR_677')
    gene_1298 = db.get('MTHFR_1298')

    if not gene_677 or not gene_1298:
        print("Error: Missing one or both MTHFR entries in the database.")
        return

    print("Building The Ultimate MTHFR Master Dashboard...")

    # Data dumps for JS
    scores_677 = json.dumps(gene_677['scores'])
    states_677 = json.dumps(gene_677['visualization_blueprint']['states'])
    
    scores_1298 = json.dumps(gene_1298['scores'])
    states_1298 = json.dumps(gene_1298['visualization_blueprint']['states'])

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MTHFR Master Analysis</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body {{ background-color: #020617; color: #f8fafc; font-family: system-ui, sans-serif; margin: 0; padding: 2rem; }}
            .app-container {{ max-width: 1100px; margin: 0 auto; }}
            
            /* Shared Styles */
            .panel {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 1.5rem; padding: 2rem; margin-bottom: 2rem; box-shadow: 0 20px 40px rgba(0,0,0,0.4); }}
            .canvas-wrapper {{ position: relative; width: 100%; height: 400px; background-color: #020617; border-radius: 1rem; border: 1px solid #1e293b; overflow: hidden; margin-top: 1.5rem; }}
            canvas {{ display: block; width: 100%; height: 100%; }}
            .path-label {{ position: absolute; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em; background: #0f172a; transform: translate(-50%, -50%); z-index: 10; white-space: nowrap; border: 1px solid #334155; }}
            
            /* Buttons */
            .btn-group {{ display: flex; gap: 0.5rem; background: #020617; padding: 0.5rem; border-radius: 1rem; border: 1px solid #334155; }}
            .geno-btn {{ flex: 1; padding: 0.75rem 1rem; border-radius: 0.5rem; font-weight: 600; color: #94a3b8; transition: all 0.2s; cursor: pointer; border: 1px solid transparent; text-align: center; font-size: 0.9rem; }}
            .geno-btn.active {{ color: #ffffff; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
            .btn-optimal.active {{ background: #22c55e; border-color: #16a34a; }}
            .btn-moderate.active {{ background: #f59e0b; border-color: #d97706; }}
            .btn-severe.active {{ background: #ef4444; border-color: #dc2626; }}
            
            /* Info Box */
            .info-box {{ background: #1e293b; border-left: 4px solid #3b82f6; padding: 1rem 1.5rem; border-radius: 0.5rem; margin-top: 1.5rem; }}
        </style>
    </head>
    <body>
        <div class="app-container">
            <div class="mb-8 text-center border-b border-slate-800 pb-6">
                <h1 class="text-4xl font-black mb-2 tracking-tight text-white">MTHFR Master Profile</h1>
                <p class="text-slate-400 text-lg">Visualizing Systemic Methylation & Neurotransmitter Recycling</p>
            </div>

            <div class="panel">
                <div class="flex justify-between items-center mb-4">
                    <div>
                        <h2 class="text-2xl font-bold text-white">The Cardiovascular Hub</h2>
                        <p class="text-slate-400 text-sm">{gene_677['variant_identity']['rsid']} (C677T) | Homocysteine & Methylation</p>
                    </div>
                </div>
                
                <div class="btn-group">
                    <button class="geno-btn btn-optimal active" onclick="set677('GG', 'optimal')">GG (Optimal)</button>
                    <button class="geno-btn btn-moderate" onclick="set677('GA', 'moderate')">GA (Moderate)</button>
                    <button class="geno-btn btn-severe" onclick="set677('AA', 'severe')">AA (Severe)</button>
                </div>

                <div class="canvas-wrapper">
                    <div class="path-label text-blue-400" style="left: 15%; top: 50%;">RAW FOLATE</div>
                    <div class="path-label text-red-400" style="left: 50%; top: 15%;">HOMOCYSTEINE CLOUD</div>
                    <div class="path-label text-green-400" style="left: 85%; top: 50%;">METHYLATION FUEL</div>
                    <div class="path-label text-slate-200" id="lbl-677-fac" style="left: 50%; top: 60%; border-color: #22c55e;">FACTORY: 100%</div>
                    <canvas id="canvas677"></canvas>
                </div>

                <div class="info-box" id="box-677">
                    <p class="text-slate-300"><strong class="text-white" id="title-677">Optimal:</strong> <span id="desc-677">{gene_677['visualization_blueprint']['states']['GG']['explanation']}</span></p>
                </div>
            </div>

            <div class="panel">
                <div class="flex justify-between items-center mb-4">
                    <div>
                        <h2 class="text-2xl font-bold text-white">The Neurological Hub</h2>
                        <p class="text-slate-400 text-sm">{gene_1298['variant_identity']['rsid']} (A1298C) | BH4 & Neurotransmitter Synthesis</p>
                    </div>
                </div>

                <div class="btn-group">
                    <button class="geno-btn btn-optimal active" onclick="set1298('TT', 'optimal')">TT (Optimal)</button>
                    <button class="geno-btn btn-moderate" onclick="set1298('TG', 'moderate')">TG (Moderate)</button>
                    <button class="geno-btn btn-severe" onclick="set1298('GG', 'severe')">GG (Severe)</button>
                </div>

                <div class="canvas-wrapper">
                    <div class="path-label text-blue-400" style="left: 15%; top: 50%;">FOLATE INPUT</div>
                    <div class="path-label text-green-400" style="left: 85%; top: 50%;">BH4 RECYCLING</div>
                    <div class="path-label text-green-400" id="lbl-1298-stat" style="left: 50%; top: 56%; border-color: #22c55e;">NORMAL FLOW</div>
                    <canvas id="canvas1298"></canvas>
                </div>

                <div class="info-box" id="box-1298">
                    <p class="text-slate-300"><strong class="text-white" id="title-1298">Optimal:</strong> <span id="desc-1298">{gene_1298['visualization_blueprint']['states']['TT']['explanation']}</span></p>
                </div>
            </div>
        </div>

        <script>
            // Data
            const scores677 = {scores_677}; const states677 = {states_677};
            const scores1298 = {scores_1298}; const states1298 = {states_1298};

            // Canvas Setup
            const c677 = document.getElementById('canvas677'); const ctx1 = c677.getContext('2d');
            const c1298 = document.getElementById('canvas1298'); const ctx2 = c1298.getContext('2d');
            
            function resize() {{
                c677.width = c677.offsetWidth; c677.height = c677.offsetHeight;
                c1298.width = c1298.offsetWidth; c1298.height = c1298.offsetHeight;
            }}
            window.addEventListener('resize', resize); resize();

            // State variables
            let cap677 = scores677['GG'] / 100.0;
            let sev1298 = 'optimal';
            
            let parts1 = []; let parts2 = [];

            // UI Controllers
            function set677(geno, sev) {{
                document.getElementById('title-677').innerText = states677[geno].label + ":";
                document.getElementById('desc-677').innerText = states677[geno].explanation;
                cap677 = scores677[geno] / 100.0;
                
                let lbl = document.getElementById('lbl-677-fac');
                lbl.innerText = "FACTORY: " + scores677[geno] + "%";
                let box = document.getElementById('box-677');
                
                if(sev === 'optimal') {{ lbl.style.color = "#4ade80"; lbl.style.borderColor = "#22c55e"; box.style.borderLeftColor = "#22c55e"; }}
                else if(sev === 'moderate') {{ lbl.style.color = "#fbbf24"; lbl.style.borderColor = "#f59e0b"; box.style.borderLeftColor = "#f59e0b"; }}
                else {{ lbl.style.color = "#f87171"; lbl.style.borderColor = "#ef4444"; box.style.borderLeftColor = "#ef4444"; }}
                
                event.target.parentElement.querySelectorAll('.geno-btn').forEach(b => b.classList.remove('active'));
                event.target.classList.add('active');
            }}

            function set1298(geno, sev) {{
                document.getElementById('title-1298').innerText = states1298[geno].label + ":";
                document.getElementById('desc-1298').innerText = states1298[geno].explanation;
                sev1298 = sev;
                
                let lbl = document.getElementById('lbl-1298-stat');
                let box = document.getElementById('box-1298');
                
                if(sev === 'optimal') {{ lbl.innerText = "NORMAL FLOW"; lbl.style.color = "#4ade80"; lbl.style.borderColor = "#22c55e"; box.style.borderLeftColor = "#22c55e"; }}
                else if(sev === 'moderate') {{ lbl.innerText = "MODERATE POOLING"; lbl.style.color = "#fbbf24"; lbl.style.borderColor = "#f59e0b"; box.style.borderLeftColor = "#f59e0b"; }}
                else {{ lbl.innerText = "SEVERE POOLING"; lbl.style.color = "#f87171"; lbl.style.borderColor = "#ef4444"; box.style.borderLeftColor = "#ef4444"; }}
                
                event.target.parentElement.querySelectorAll('.geno-btn').forEach(b => b.classList.remove('active'));
                event.target.classList.add('active');
            }}

            // --- ENGINE 1: Supply Chain (677) ---
            class Part1 {{
                constructor() {{
                    this.x = -10; this.y = c677.height / 2 + (Math.random() - 0.5) * 20;
                    this.vx = 2 + Math.random(); this.vy = 0;
                    this.state = 'raw'; this.color = '#60a5fa';
                    this.oX = c677.width / 2; this.oY = c677.height * 0.25;
                    this.a = Math.random() * Math.PI * 2; this.r = 10 + Math.random() * 50;
                }}
                update() {{
                    if(this.state === 'dead') return;
                    if(this.state === 'raw') {{
                        this.x += this.vx; this.y += this.vy;
                        if(this.x >= c677.width / 2 - 15) {{
                            if(Math.random() <= cap677) {{ this.state = 'fuel'; this.color = '#4ade80'; this.vx = 3+Math.random()*2; }}
                            else {{ this.state = 'toxin'; this.color = '#f87171'; }}
                        }}
                    }} else if(this.state === 'fuel') {{
                        this.x += this.vx; if(this.x > c677.width + 10) this.state = 'dead';
                    }} else if(this.state === 'toxin') {{
                        this.a += 0.02 + Math.random() * 0.03;
                        this.x += (this.oX + Math.cos(this.a) * this.r - this.x) * 0.05;
                        this.y += (this.oY + Math.sin(this.a) * this.r - this.y) * 0.05;
                    }}
                }}
                draw(ctx) {{
                    if(this.state === 'dead') return;
                    ctx.beginPath(); ctx.arc(this.x, this.y, 4, 0, Math.PI*2);
                    ctx.fillStyle = this.color; ctx.shadowBlur = 8; ctx.shadowColor = this.color; ctx.fill(); ctx.shadowBlur = 0;
                }}
            }}

            // --- ENGINE 2: Figure 8 (1298) ---
            function get8Pos(t) {{
                return {{ x: c1298.width/2 + (c1298.width*0.3) * Math.sin(t), y: c1298.height/2 + (c1298.height*0.25) * Math.sin(t) * Math.cos(t) }};
            }}
            class Part2 {{
                constructor() {{
                    this.t = 1.5 * Math.PI; this.s = 0.006 + Math.random() * 0.003;
                    this.state = 'raw'; this.color = '#60a5fa'; this.laps = 0;
                    this.oX = (Math.random()-0.5)*40; this.oY = (Math.random()-0.5)*40; this.w = 2+Math.random()*4;
                }}
                update() {{
                    if(this.state === 'dead') return;
                    let pt = this.t; this.t += this.s;
                    if(this.t >= 2*Math.PI) {{
                        this.t -= 2*Math.PI;
                        if(this.state === 'raw') {{
                            this.state = 'bh4'; this.color = '#4ade80';
                            let fr = sev1298 === 'moderate' ? 0.4 : (sev1298 === 'severe' ? 0.85 : 0);
                            if(Math.random() < fr) {{
                                this.laps = sev1298 === 'severe' ? 6 : 3;
                                this.color = sev1298 === 'severe' ? '#ef4444' : '#f59e0b';
                            }}
                        }}
                    }}
                    if(this.state === 'bh4' && pt < Math.PI && this.t >= Math.PI) {{
                        if(this.laps > 0) {{ this.t -= Math.PI; this.laps--; }} else {{ this.state = 'dead'; }}
                    }}
                }}
                draw(ctx) {{
                    if(this.state === 'dead') return;
                    let p = get8Pos(this.t);
                    if(this.laps > 0) {{ p.x += this.oX * Math.sin(this.t*this.w); p.y += this.oY * Math.cos(this.t*this.w); }}
                    ctx.beginPath(); ctx.arc(p.x, p.y, 5, 0, Math.PI*2);
                    ctx.fillStyle = this.color; ctx.shadowBlur = this.laps > 0 ? 12 : 6; ctx.shadowColor = this.color; ctx.fill(); ctx.shadowBlur = 0;
                }}
            }}

            function drawHex(ctx, x, y, c) {{
                ctx.beginPath(); for(let i=0; i<6; i++) ctx[i===0?'moveTo':'lineTo'](x+35*Math.cos(Math.PI/3*i+Math.PI/6), y+35*Math.sin(Math.PI/3*i+Math.PI/6));
                ctx.closePath(); ctx.fillStyle="rgba(15,23,42,0.9)"; ctx.fill(); ctx.lineWidth=3; ctx.strokeStyle=c; ctx.shadowBlur=20; ctx.shadowColor=c; ctx.stroke();
                ctx.shadowBlur=0; ctx.fillStyle=c; ctx.font="bold 12px sans-serif"; ctx.textAlign="center"; ctx.textBaseline="middle"; ctx.fillText("MTHFR",x,y);
            }}

            // Master Loop
            function animate() {{
                // Panel 1
                ctx1.clearRect(0,0,c677.width,c677.height);
                ctx1.beginPath(); ctx1.moveTo(0, c677.height/2); ctx1.lineTo(c677.width, c677.height/2);
                ctx1.strokeStyle='#334155'; ctx1.lineWidth=2; ctx1.setLineDash([5,10]); ctx1.stroke(); ctx1.setLineDash([]);
                
                if(parts1.length < 250 && Math.random() < 0.2) parts1.push(new Part1());
                let tox=0;
                for(let i=parts1.length-1; i>=0; i--) {{
                    parts1[i].update(); parts1[i].draw(ctx1);
                    if(parts1[i].state === 'toxin') tox++;
                    if(parts1[i].state === 'dead' || tox > 120) {{ if(parts1[i].state==='toxin') tox--; parts1.splice(i,1); }}
                }}
                drawHex(ctx1, c677.width/2, c677.height/2, cap677 > 0.8 ? '#22c55e' : (cap677 > 0.4 ? '#f59e0b' : '#ef4444'));

                // Panel 2
                ctx2.clearRect(0,0,c1298.width,c1298.height);
                ctx2.beginPath(); for(let i=0; i<=Math.PI*2; i+=0.05) {{ let p = get8Pos(i); ctx2[i===0?'moveTo':'lineTo'](p.x, p.y); }}
                ctx2.strokeStyle='#334155'; ctx2.lineWidth=2; ctx2.setLineDash([6,10]); ctx2.stroke(); ctx2.setLineDash([]);
                
                if(parts2.length < 200 && Math.random() < 0.1) parts2.push(new Part2());
                for(let i=parts2.length-1; i>=0; i--) {{
                    parts2[i].update(); parts2[i].draw(ctx2);
                    if(parts2[i].state === 'dead') parts2.splice(i,1);
                }}
                drawHex(ctx2, c1298.width/2, c1298.height/2, sev1298==='optimal' ? '#22c55e' : (sev1298==='moderate' ? '#f59e0b' : '#ef4444'));

                requestAnimationFrame(animate);
            }}
            animate();
        </script>
    </body>
    </html>
    """
    
    filename = "MTHFR_Master_Report.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    print(f"Success! Generated combined interactive report: {filename}")

if __name__ == "__main__":
    generate_master_report('mthfr_database.json')