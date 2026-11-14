import json, sys, numpy as np
from PIL import Image, ImageDraw, ImageFont
out = sys.argv[1]
S = 1024
atlas = np.frombuffer(open(f"{out}/atlas.rgba","rb").read(), np.uint8).reshape(S, S, 4)[::-1].astype(np.float32)/255  # top row first
# atlas preview over a checker
chk = ((np.indices((S,S)).sum(0)//32)%2)[...,None]*0.15+0.75
prev = atlas[...,:3]*atlas[...,3:]+chk*(1-atlas[...,3:])
Image.fromarray((prev*255).astype(np.uint8)).save(f"{out}/atlas.png")
d = json.load(open(f"{out}/frames.json"))
W = H = 260; FOV = 40
def lin(c): return np.where(c<=0.04045, c/12.92, ((c+0.055)/1.055)**2.4)
def srgb(c): c=np.clip(c,0,1); return np.where(c<=0.0031308, c*12.92, 1.055*c**(1/2.4)-0.055)
def camera(cam):
    p = np.array(cam[:3]); look = np.array(cam[3:]); f = look-p; f/=np.linalg.norm(f)
    r = np.cross([0,1,0], f); r/=np.linalg.norm(r); u = np.cross(f, r)
    foc = (H/2)/np.tan(np.radians(FOV/2))
    def proj(P):
        q = P-p; z = q@f
        return np.stack([W/2 + (q@r)/z*foc, H/2 - (q@u)/z*foc, z], -1)
    return proj
def render(fx, fr):
    proj = camera(fx["cam"])
    img = np.zeros((H,W,3), np.float32); img[:] = lin(np.array([0.984,0.961,0.902]))  # paper
    pil = Image.fromarray((srgb(img)*255).astype(np.uint8)); dr = ImageDraw.Draw(pil)
    # page grid (y=0) every 0.1 art
    for k in np.arange(-0.5,0.51,0.1):
        for a,b in (([k,0,-0.6],[k,0,0.6]),([-0.5,0,k],[0.5,0,k])):
            A=proj(np.array(a)); B=proj(np.array(b))
            if A[2]>0 and B[2]>0: dr.line([A[0],A[1],B[0],B[1]], fill=(225,212,180), width=1)
    # scale figures: David 0.30 tall at (-0.25,0,0.1)-ish, Goliath 0.80 at (0.15,0,-0.25)
    for base,h,c in (([-0.3,0,0.1],0.30,(120,160,210)),([0.15,0,-0.25],0.80,(190,150,110))):
        A=proj(np.array(base)); B=proj(np.array(base)+[0,h,0])
        if A[2]>0: dr.line([A[0],A[1],B[0],B[1]], fill=c, width=5)
    img = lin(np.asarray(pil).astype(np.float32)/255)
    v = np.array(fr["v"], np.float32).reshape(-1,9)
    if len(v):
        P = proj(v[:,:3].astype(np.float64))
        for tris, add in ((fr["a"],False),(fr["b"],True)):
            t = np.array(tris).reshape(-1,3)
            for tri in t:
                q = P[tri]
                if (q[:,2]<=0.01).any(): continue
                x0,y0 = np.floor(q[:,:2].min(0)).astype(int); x1,y1 = np.ceil(q[:,:2].max(0)).astype(int)
                x0=max(x0,0);y0=max(y0,0);x1=min(x1,W-1);y1=min(y1,H-1)
                if x1<x0 or y1<y0: continue
                ys,xs = np.mgrid[y0:y1+1,x0:x1+1]+0.5
                (ax,ay),(bx,by),(cx,cy) = q[0,:2],q[1,:2],q[2,:2]
                den = (by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
                if abs(den)<1e-9: continue
                w0=((by-cy)*(xs-cx)+(cx-bx)*(ys-cy))/den; w1=((cy-ay)*(xs-cx)+(ax-cx)*(ys-cy))/den; w2=1-w0-w1
                m=(w0>=0)&(w1>=0)&(w2>=0)
                if not m.any(): continue
                # perspective-correct interpolation
                iz = np.array([1/q[0,2],1/q[1,2],1/q[2,2]])
                ww = np.stack([w0*iz[0],w1*iz[1],w2*iz[2]],-1); ww/=ww.sum(-1,keepdims=True)
                attr = v[tri,3:]  # u v r g b a
                A_ = ww@attr
                uu = np.clip((A_[...,0]*S).astype(int),0,S-1); vv = np.clip(((1-A_[...,1])*S).astype(int),0,S-1)
                tex = atlas[vv,uu]
                col = lin(tex[...,:3])*lin(A_[...,2:5]); a = tex[...,3]*A_[...,5]
                a = np.where(m,a,0)[...,None]
                reg = img[y0:y1+1,x0:x1+1]
                img[y0:y1+1,x0:x1+1] = reg + col*a if add else reg*(1-a)+col*a
    return Image.fromarray((srgb(img)*255).astype(np.uint8))

# ---- Ruth rows (run.sh ruth): stand-in Bethlehem set + actors with a depth buffer, multiplied by the frame's StoryTint
def hexc(h): h=h.lstrip('#'); return np.array([int(h[i:i+2],16)/255 for i in (0,2,4)])
def box(c, sx, sy, sz_, col, top=None):
    x,y,z = c; X=[x-sx/2,x+sx/2]; Y=[y,y+sy]; Z=[z-sz_/2,z+sz_/2]
    P=lambda i,j,k: [X[i],Y[j],Z[k]]
    q=[(P(0,0,1),P(1,0,1),P(1,1,1),P(0,1,1),col*0.92),(P(1,0,0),P(1,0,1),P(1,1,1),P(1,1,0),col*0.8),
       (P(0,0,0),P(0,0,1),P(0,1,1),P(0,1,0),col*0.8),(P(0,1,0),P(1,1,0),P(1,1,1),P(0,1,1),top if top is not None else col)]
    return q
def ruth_scene(actors, cam):
    Q=[]  # quads (4 corners, colour sRGB)
    Q.append(([-0.6,0,-0.5875],[0.6,0,-0.5875],[0.6,0,0.21],[-0.6,0,0.21],hexc('#D9B77A')))          # ground
    Q.append(([-0.6,0.001,0.15],[-0.20,0.001,0.12],[-0.20,0.001,0.17],[-0.6,0.001,0.21],hexc('#E9D9B6')))  # road
    Q.append(([0.20,0.002,-0.22],[0.54,0.002,-0.22],[0.54,0.002,0.0],[0.20,0.002,0.0],hexc('#C9963A')))     # field floor
    for i in range(12):                                                                                      # far + near hills
        x0=-0.6+i*0.1; x1=x0+0.1
        h0=0.27+0.03*np.sin(x0*7); h1=0.27+0.03*np.sin(x1*7)
        Q.append(([x0,0,-0.585],[x1,0,-0.585],[x1,h1,-0.585],[x0,h0,-0.585],hexc('#8FA9A0')))
        h0=0.17+0.04*np.sin(x0*9+1); h1=0.17+0.04*np.sin(x1*9+1)
        Q.append(([x0,0,-0.56],[x1,0,-0.56],[x1,h1,-0.56],[x0,h0,-0.56],hexc('#A7B86A')))
    Q+=box((-0.30,0,-0.44),0.28,0.20,0.20,hexc('#D9C29A'),hexc('#C9A77A'))                                  # house
    Q.append(([-0.33,0,-0.339],[-0.27,0,-0.339],[-0.27,0.11,-0.339],[-0.33,0.11,-0.339],hexc('#8A5A3B')))  # door
    Q+=box((0.30,0,-0.44),0.26,0.012,0.26,hexc('#B9B4AA'))                                                 # threshing rim
    Q+=box((0.30,0,-0.46),0.12,0.05,0.10,hexc('#E8B84A'))                                                  # grain heap
    Q+=box((0.40,0,-0.40),0.03,0.04,0.03,hexc('#C8643C'))                                                  # lamp stone/lamp
    for i in range(7):                                                                                       # barley clumps
        for j in range(4):
            Q+=box((0.22+i*0.05,0,-0.20+j*0.06),0.03,0.08,0.03,hexc('#E8B84A'),hexc('#F0CC6A'))
    Q+=box((-0.44,0,-0.10),0.04,0.17,0.04,hexc('#7A6650'))                                                 # olive trunk
    Q+=box((-0.44,0.17,-0.10),0.20,0.10,0.20,hexc('#8FA876'))                                              # olive crown
    # actors: camera-facing slabs with a head
    p=np.array(cam[:3]); look=np.array(cam[3:]); f=look-p; f/=np.linalg.norm(f); r=np.cross([0,1,0],f); r/=np.linalg.norm(r)
    for (x,z,h,c) in actors:
        col=hexc(c); w=h*0.22; base=np.array([x,0,z])
        for (y0,y1,ww,cc) in ((0,h*0.82,w,col),(h*0.80,h,w*0.62,hexc('#E8C4A0'))):
            a=base+[0,y0,0]-r*ww/2; b=base+[0,y0,0]+r*ww/2
            Q.append((list(a),list(b),list(b+[0,y1-y0,0]),list(a+[0,y1-y0,0]),cc))
    return Q
def raster(img, zb, q3, P, attr_fn, add=False, write_z=False, test_z=False):
    q = P
    if (q[:,2]<=0.01).any(): return
    x0,y0 = np.floor(q[:,:2].min(0)).astype(int); x1,y1 = np.ceil(q[:,:2].max(0)).astype(int)
    x0=max(x0,0);y0=max(y0,0);x1=min(x1,W-1);y1=min(y1,H-1)
    if x1<x0 or y1<y0: return
    ys,xs = np.mgrid[y0:y1+1,x0:x1+1]+0.5
    (ax,ay),(bx,by),(cx,cy) = q[0,:2],q[1,:2],q[2,:2]
    den = (by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
    if abs(den)<1e-9: return
    w0=((by-cy)*(xs-cx)+(cx-bx)*(ys-cy))/den; w1=((cy-ay)*(xs-cx)+(ax-cx)*(ys-cy))/den; w2=1-w0-w1
    m=(w0>=0)&(w1>=0)&(w2>=0)
    if not m.any(): return
    iz = np.array([1/q[0,2],1/q[1,2],1/q[2,2]])
    ww = np.stack([w0*iz[0],w1*iz[1],w2*iz[2]],-1); zpix = 1/ww.sum(-1); ww = ww*zpix[...,None]
    reg = zb[y0:y1+1,x0:x1+1]
    if test_z: m &= zpix < reg + 1e-4
    if write_z:
        m &= zpix < reg
        reg[m] = zpix[m]
        img[y0:y1+1,x0:x1+1][m] = attr_fn(ww)[m]; return
    col, a = attr_fn(ww)
    a = np.where(m,a,0)[...,None]
    ri = img[y0:y1+1,x0:x1+1]
    img[y0:y1+1,x0:x1+1] = ri + col*a if add else ri*(1-a)+col*a
def render_ruth(fx, fr):
    proj = camera(fx["cam"])
    img = np.zeros((H,W,3), np.float32); img[:] = lin(np.array([0.93,0.93,0.93]))   # the room around the page
    zb = np.full((H,W), 1e9)
    scene = babylon_scene(fx["actors"], fx["cam"], fx.get("shut", False)) if fx.get("scene")=="daniel" else ruth_scene(fx["actors"], fx["cam"])
    if fx.get("scene")=="exodus": scene = egypt_scene(fx["actors"], fx["cam"], fr.get("wall", 0), fr.get("lane", True))   # Exodus rows
    if fx.get("scene")=="prodigal": scene = homeland_scene(fx["actors"], fx["cam"])   # Prodigal rows
    if fx.get("scene")=="gabriel": scene = heaven_scene(fx["actors"], fx["cam"], fr.get("lift", 0), fx.get("wings", 1))   # Gabriel rows
    for (*corners, col) in scene:
        C = np.array(corners, np.float64); Pq = proj(C); cl = lin(col).astype(np.float32)
        for tri in ((0,1,2),(0,2,3)):
            raster(img, zb, None, Pq[list(tri)], lambda ww, cl=cl: np.broadcast_to(cl, ww.shape[:2]+(3,)), write_z=True)
    tint = np.array(fr.get("tint",[1,1,1]))
    img *= lin(tint).astype(np.float32)          # StoryTintStage multiply overlay (applies to set, actors, room)
    v = np.array(fr["v"], np.float32).reshape(-1,9)
    if len(v):
        P = proj(v[:,:3].astype(np.float64))
        for tris, add in ((fr["a"],False),(fr["b"],True)):
            for tri in np.array(tris).reshape(-1,3):
                attr = v[tri,3:]
                def fn(ww, attr=attr):
                    A_ = ww@attr
                    uu = np.clip((A_[...,0]*S).astype(int),0,S-1); vv = np.clip(((1-A_[...,1])*S).astype(int),0,S-1)
                    tex = atlas[vv,uu]
                    return lin(tex[...,:3])*lin(A_[...,2:5]), tex[...,3]*A_[...,5]
                raster(img, zb, None, P[tri], fn, add=add, test_z=True)
    return Image.fromarray((srgb(img)*255).astype(np.uint8))
# ---- Daniel rows (run.sh daniel): stand-in Babylon (docs/daniel/CONTRACT.md §6) + actors (5th value = slab width)
def babylon_scene(actors, cam, shut):
    Q=[]
    Q.append(([-0.6,0,-0.5875],[0.6,0,-0.5875],[0.6,0,0.21],[-0.6,0,0.21],hexc('#E6CF9E')))             # sandy courtyard
    Q.append(([-0.40,0.001,-0.30],[0.40,0.001,-0.30],[0.40,0.001,0.18],[-0.40,0.001,0.18],hexc('#D8C6A4'))) # paving
    for i in range(12):                                                                                    # city wall + crenellations
        x0=-0.6+i*0.1; x1=x0+0.1
        Q+=box(((x0+x1)/2,0,-0.575),0.1,0.26,0.03,hexc('#D9B98A'),hexc('#E2C89E'))
        Q+=box((x0+0.03,0.26,-0.575),0.04,0.03,0.03,hexc('#D9B98A'))
    Q.append(([-0.06,0,-0.559],[0.06,0,-0.559],[0.06,0.20,-0.559],[-0.06,0.20,-0.559],hexc('#3F74B8')))  # blue gate
    Q+=box((0,0,-0.46),0.32,0.04,0.20,hexc('#CDB48A'),hexc('#E0CBA0'))                                    # dais
    for x in (-0.12,0.12): Q+=box((x,0.04,-0.48),0.03,0.22,0.03,hexc('#E9DCC0'))                          # columns
    Q+=box((0,0.26,-0.48),0.30,0.03,0.12,hexc('#3F74B8'))                                                 # canopy / frieze
    Q+=box((0,0.04,-0.50),0.07,0.10,0.05,hexc('#E8B84A'))                                                 # throne
    Q+=box((-0.15,0,-0.36),0.012,0.17,0.012,hexc('#7A5A3A'))                                              # torch pole
    Q+=box((-0.44,0,-0.44),0.24,0.26,0.20,hexc('#E2C79A'),hexc('#CBA978'))                                # house
    Q+=box((-0.54,0,-0.14),0.02,0.16,0.20,hexc('#D9BC8C'))                                                # window wall
    Q.append(([-0.53,0.06,-0.17],[-0.53,0.06,-0.11],[-0.53,0.14,-0.11],[-0.53,0.14,-0.17],hexc('#6A4A35'))) # window
    Q.append(([-0.48,0.002,-0.19],[-0.40,0.002,-0.19],[-0.40,0.002,-0.09],[-0.48,0.002,-0.09],hexc('#C0504A'))) # rug
    Q+=box((-0.29,0,-0.07),0.025,0.30,0.025,hexc('#8A6A48'))                                              # palm trunk
    Q+=box((-0.29,0.28,-0.07),0.18,0.05,0.18,hexc('#6F9A55'))                                             # palm crown
    Q+=box((0.52,0,0.15),0.10,0.10,0.07,hexc('#E07B5A'),hexc('#F2C14E'))                                  # market stall
    # den: sandy floor + a ring of stone blocks, opening toward (-0.74, 0.67)
    cx,cz=0.38,-0.17
    Q.append(([cx-0.17,0.0015,cz-0.17],[cx+0.17,0.0015,cz-0.17],[cx+0.17,0.0015,cz+0.17],[cx-0.17,0.0015,cz+0.17],hexc('#D7BE8A')))
    op=np.arctan2(0.67,-0.74)
    for k in range(20):
        a=2*np.pi*k/20
        if abs((a-op+np.pi)%(2*np.pi)-np.pi)<0.36: continue
        Q+=box((cx+0.175*np.cos(a),0,cz+0.175*np.sin(a)),0.055,0.075,0.055,hexc('#B9AE9A'),hexc('#CFC6B4'))
    if shut: Q+=box((0.25,0,-0.05),0.10,0.11,0.06,hexc('#A9A294'),hexc('#BDB6A8'))                        # stoneShut
    else:    Q+=box((0.18,0,-0.13),0.10,0.11,0.06,hexc('#A9A294'),hexc('#BDB6A8'))                        # stoneOpen
    p=np.array(cam[:3]); look=np.array(cam[3:]); f=look-p; f/=np.linalg.norm(f); r=np.cross([0,1,0],f); r/=np.linalg.norm(r)
    for (x,z,h,c,*rest) in actors:
        col=hexc(c); w=rest[0] if rest and rest[0]>0 else h*0.22; base=np.array([x,0,z])
        hw=w*(0.45 if rest and rest[0]>0 else 0.62)
        for (y0,y1,ww,cc) in ((0,h*0.82,w,col),(h*0.80,h,hw,hexc('#E8C4A0') if not (rest and rest[0]>0) else col*0.85)):
            a=base+[0,y0,0]-r*ww/2; b=base+[0,y0,0]+r*ww/2
            Q.append((list(a),list(b),list(b+[0,y1-y0,0]),list(a+[0,y1-y0,0]),cc))
    return Q
# ---- Exodus rows (run.sh exodus): stand-in Egypt (docs/exodus/CONTRACT.md §6); walls at the frame's scale, lane shown or not
def egypt_scene(actors, cam, wall, lane):
    Q=[]
    Q.append(([-0.6,0,-0.5875],[0.6,0,-0.5875],[0.6,0,0.21],[-0.6,0,0.21],hexc('#EBD3A0')))              # sand
    Q.append(([-0.60,0.010,-0.30],[-0.50,0.010,-0.30],[-0.50,0.010,0.21],[-0.60,0.010,0.21],hexc('#3E8FC4')))  # nile
    for i in range(12):                                                                                    # dunes
        x0=-0.6+i*0.1; x1=x0+0.1; h0=0.10+0.03*np.sin(x0*8); h1=0.10+0.03*np.sin(x1*8)
        Q.append(([x0,0,-0.57],[x1,0,-0.57],[x1,h1,-0.57],[x0,h0,-0.57],hexc('#E2BE7A')))
    for x in (-0.50,-0.30):                                                                                # pyramids (flat)
        Q.append(([x-0.08,0,-0.565],[x+0.08,0,-0.565],[x+0.001,0.22,-0.565],[x-0.001,0.22,-0.565],hexc('#E2BE7A')*0.95))
    Q+=box((0.35,0,-0.50),0.50,0.30,0.18,hexc('#B5643F'),hexc('#C9805A'))                                 # mountain
    Q+=box((-0.36,0,-0.44),0.38,0.03,0.12,hexc('#E3C998'))                                                # dais
    for x in (-0.50,-0.41,-0.31,-0.22): Q+=box((x,0.03,-0.47),0.03,0.20,0.03,hexc('#EFE0BE'))           # columns
    Q+=box((-0.36,0.23,-0.47),0.36,0.03,0.06,hexc('#E0B13A'))                                             # lintel
    for x in (-0.08,0.04):                                                                                 # houses + doors
        Q+=box((x,0,-0.47),0.11,0.10,0.12,hexc('#C99A6B'),hexc('#B88A5B'))
        Q.append(([x-0.02,0,-0.409],[x+0.02,0,-0.409],[x+0.02,0.07,-0.409],[x-0.02,0.07,-0.409],hexc('#4A2E1F')))
    Q+=box((-0.36,0,-0.11),0.18,0.05,0.12,hexc('#A9673F'))                                                # bricks
    Q+=box((0.14,0,-0.36),0.10,0.03,0.08,hexc('#B5643F'))                                                 # rise
    Q+=box((0.14,0.03,-0.36),0.07,0.08,0.06,hexc('#5E4330'),hexc('#8FA876'))                              # bush
    Q.append(([0.40,0.002,-0.5875],[0.60,0.002,-0.5875],[0.60,0.002,0.21],[0.40,0.002,0.21],hexc('#F1E2BC')))  # far shore
    Q.append(([0.20,0.001,0.02],[0.40,0.001,0.02],[0.40,0.001,0.13],[0.20,0.001,0.13],hexc('#C8A97A')))   # sea-bed
    Q.append(([0.20,0.010,-0.24],[0.40,0.010,-0.24],[0.40,0.010,0.02],[0.20,0.010,0.02],hexc('#2C7FA8')))  # seaWaterBack
    Q.append(([0.20,0.010,0.13],[0.40,0.010,0.13],[0.40,0.010,0.21],[0.20,0.010,0.21],hexc('#2C7FA8')))    # seaWaterFront
    if lane: Q.append(([0.20,0.010,0.02],[0.40,0.010,0.02],[0.40,0.010,0.13],[0.20,0.010,0.13],hexc('#2F86AE')))  # seaWaterLane
    if wall>0:
        Q+=box((0.30,0,0.0075),0.20,0.24*wall,0.025,hexc('#4FB3C9'),hexc('#8AD3E2'))                     # seaWallBack
        Q+=box((0.30,0,0.1425),0.20,0.14*wall,0.025,hexc('#4FB3C9'),hexc('#8AD3E2'))                     # seaWallFront
    for x in (0.46,0.52,0.57): Q+=box((x,0,-0.30),0.02,0.22,0.02,hexc('#8A6A44'))                         # palms
    p=np.array(cam[:3]); look=np.array(cam[3:]); f=look-p; f/=np.linalg.norm(f); r=np.cross([0,1,0],f); r/=np.linalg.norm(r)
    for (x,z,h,c) in actors:
        col=hexc(c); w=h*0.22; base=np.array([x,0,z])
        for (y0,y1,ww,cc) in ((0,h*0.82,w,col),(h*0.80,h,w*0.62,hexc('#E8C4A0'))):
            a=base+[0,y0,0]-r*ww/2; b=base+[0,y0,0]+r*ww/2
            Q.append((list(a),list(b),list(b+[0,y1-y0,0]),list(a+[0,y1-y0,0]),cc))
    return Q
# ---- Prodigal rows (run.sh prodigal): stand-in homeland (docs/prodigal/CONTRACT.md §6)
def homeland_scene(actors, cam):
    Q=[]
    Q.append(([-0.6,0,-0.5875],[0.0,0,-0.5875],[0.0,0,0.21],[-0.6,0,0.21],hexc('#C9C98A')))               # grassy sand (home)
    Q.append(([0.0,0,-0.5875],[0.6,0,-0.5875],[0.6,0,0.21],[0.0,0,0.21],hexc('#D9BE8A')))                 # dry earth (far)
    for (a,b) in (((-0.10,-0.06),(0.04,0.02)),((0.04,0.02),(0.16,0.08)),((0.16,0.08),(0.20,0.21)),((0.04,0.02),(0.30,-0.22))):   # road
        d=np.array(b)-np.array(a); n=np.array([-d[1],d[0]])/np.linalg.norm(d)*0.03
        Q.append(([a[0]-n[0],0.001,a[1]-n[1]],[b[0]-n[0],0.001,b[1]-n[1]],[b[0]+n[0],0.001,b[1]+n[1]],[a[0]+n[0],0.001,a[1]+n[1]],hexc('#E9D9B6')))
    Q.append(([-0.52,0.0015,-0.36],[-0.08,0.0015,-0.36],[-0.08,0.0015,0.02],[-0.52,0.0015,0.02],hexc('#D9C29A')))  # courtyard
    for i in range(12):                                                                                    # hills: green left, tawny right
        x0=-0.6+i*0.1; x1=x0+0.1; h0=0.20+0.05*np.sin(x0*7); h1=0.20+0.05*np.sin(x1*7)
        Q.append(([x0,0,-0.565],[x1,0,-0.565],[x1,h1,-0.565],[x0,h0,-0.565],hexc('#A7C26A' if x0<0 else '#D9B77A')))
    Q+=box((-0.38,0,-0.47),0.28,0.20,0.16,hexc('#E3D3B0'),hexc('#C9A77A'))                                # house
    Q.append(([-0.41,0,-0.389],[-0.35,0,-0.389],[-0.35,0.11,-0.389],[-0.41,0.11,-0.389],hexc('#8A5A3B')))  # door
    Q+=box((-0.46,0,-0.04),0.08,0.04,0.08,hexc('#A9A49A'))                                                # well
    Q+=box((-0.50,0,-0.28),0.025,0.20,0.025,hexc('#7A5A3A')); Q+=box((-0.50,0.18,-0.28),0.14,0.07,0.14,hexc('#5E9A4A'))  # fig
    Q+=box((-0.54,0,-0.16),0.02,0.04,0.38,hexc('#CDBB98'))                                                # west wall
    Q.append(([-0.06,0.002,-0.52],[0.24,0.002,-0.52],[0.24,0.002,-0.28],[-0.06,0.002,-0.28],hexc('#9A6A43')))  # field
    for j in range(4): Q+=box((0.09,0,-0.50+j*0.03),0.28,0.03,0.008,hexc('#B7C25A'))                     # wheat rows
    Q+=box((0.40,0,-0.50),0.30,0.12,0.08,hexc('#F1EADB'))                                                 # tavern back room
    for x in (0.27,0.53): Q+=box((x,0,-0.40),0.02,0.20,0.02,hexc('#F1EADB'))                              # columns
    Q+=box((0.40,0.20,-0.43),0.32,0.015,0.14,hexc('#D2483A'),hexc('#E86A5A'))                             # awning
    Q+=box((0.54,0,-0.32),0.08,0.08,0.05,hexc('#E07B5A'),hexc('#F2C14E'))                                 # market stall
    Q.append(([0.26,0.0015,-0.06],[0.56,0.0015,-0.06],[0.56,0.0015,0.18],[0.26,0.0015,0.18],hexc('#7A5638')))  # pen mud
    for (x,z,sx,sz_) in ((0.42,-0.06,0.28,0.01),(0.26,-0.03,0.01,0.06),(0.26,0.17,0.01,0.02),(0.41,0.18,0.30,0.01),(0.56,0.06,0.01,0.24)):
        Q+=box((x,0,z),sx,0.05,sz_,hexc('#9B6B43'))                                                       # fence with gaps
    Q+=box((0.48,0,0.10),0.08,0.025,0.03,hexc('#8A6A44'),hexc('#6B4426'))                                 # trough + pods
    for (x,z) in ((0.45,0.00),(0.52,0.03),(0.46,0.15),(0.53,0.14)): Q+=box((x,0,z),0.05,0.035,0.035,hexc('#F2A7A0'))   # pigs
    p=np.array(cam[:3]); look=np.array(cam[3:]); f=look-p; f/=np.linalg.norm(f); r=np.cross([0,1,0],f); r/=np.linalg.norm(r)
    for (x,z,h,c) in actors:
        col=hexc(c); w=h*0.22; base=np.array([x,0,z])
        for (y0,y1,ww,cc) in ((0,h*0.82,w,col),(h*0.80,h,w*0.62,hexc('#E2A878'))):
            a=base+[0,y0,0]-r*ww/2; b=base+[0,y0,0]+r*ww/2
            Q.append((list(a),list(b),list(b+[0,y1-y0,0]),list(a+[0,y1-y0,0]),cc))
    return Q
# ---- Gabriel rows (run.sh gabriel): stand-in heaven (docs/gabriel/CONTRACT.md §6); the actor is lifted by the frame's "lift"
def heaven_scene(actors, cam, lift, wings):
    Q=[]
    Q.append(([-0.6,0.035,-0.5875],[0.6,0.035,-0.5875],[0.6,0.035,0.21],[-0.6,0.035,0.21],hexc('#FFF6E2')))        # cloud floor
    Q.append(([-0.6,0.036,-0.5875],[0.6,0.036,-0.5875],[0.6,0.036,-0.30],[-0.6,0.036,-0.30],hexc('#F7DDB0')))      # far clouds
    for k in range(7):                                                                                            # higher lumps at the edges
        z=-0.52+k*0.11; h=0.07+0.03*np.sin(k*2.1)
        for sx in (-1,1): Q+=box((sx*0.53,0,z),0.14,h,0.10,hexc('#FBEBCB'),hexc('#FFF6E2'))
    Q+=box((0,0,-0.545),1.20,0.30,0.09,hexc('#F6EEDC'),hexc('#EFE2C4'))                                           # wall, front face z -0.50
    for x in (-0.50,0.50): Q+=box((x,0,-0.54),0.10,0.38,0.10,hexc('#F2E8D2'),hexc('#EED48E'))                     # towers
    Q+=box((0,0,-0.54),0.30,0.42,0.10,hexc('#F6EEDC'),hexc('#EED48E'))                                            # gate house
    for x in (-0.11,0.11): Q+=box((x,0,-0.485),0.03,0.24,0.03,hexc('#EED48E'))                                    # columns
    Q.append(([-0.07,0.04,-0.489],[0.07,0.04,-0.489],[0.07,0.21,-0.489],[-0.07,0.21,-0.489],hexc('#FBE3A6')))      # arch opening
    Q.append(([-0.035,0.265,-0.489],[0.035,0.265,-0.489],[0.035,0.335,-0.489],[-0.035,0.335,-0.489],hexc('#F2A43A'))) # rosette glow
    for k in range(5): Q+=box((0,0,-0.468+k*0.024),0.30+0.02*k,0.115-0.018*k,0.024,hexc('#F3E9D3'),hexc('#FBF3E0')) # 5 steps to z -0.36
    for (x,z,y) in ((-0.45,-0.30,0.18),(0.45,-0.28,0.20)):                                                        # floating islets
        b_=box((x,y,z),0.18,0.07,0.14,hexc('#C9A47A'),hexc('#7DAA55')); Q+=b_
        Q+=box((x+0.03,y+0.07,z),0.05,0.06,0.05,hexc('#6F9A4A'))
    for sx in (-1,1): Q+=box((sx*0.50,0,0.16),0.18,0.09,0.09,hexc('#FFFBF0'),hexc('#FFFFFF'))                     # front clouds
    p=np.array(cam[:3]); look=np.array(cam[3:]); f=look-p; f/=np.linalg.norm(f); r=np.cross([0,1,0],f); r/=np.linalg.norm(r)
    for (x,z,h,c) in actors:
        base=np.array([x,lift,z]); col=hexc(c)
        def slab(y0,y1,w,cc,back=0.0):
            a=base+[0,y0,0]-r*w/2+f*back; b=base+[0,y0,0]+r*w/2+f*back
            Q.append((list(a),list(b),list(b+[0,y1-y0,0]),list(a+[0,y1-y0,0]),cc))
        if wings>0:                                                                                               # spread wings: span 1.0, tips to 0.80
            for sx in (-1,1):
                P=lambda u,y: list(base+r*(sx*u)+np.array([0,y,0])+f*0.03)
                Q.append((P(0.05,0.30),P(0.50,0.50),P(0.47,0.80),P(0.05,0.52),hexc('#FFFDF6')*0.97))
                Q.append((P(0.05,0.30),P(0.30,0.24),P(0.50,0.50),P(0.05,0.40),hexc('#F3EAD6')))
        slab(0,0.24,0.10,hexc('#E6B23E'))                                                                         # greaves
        slab(0.24,0.50,0.135,col); slab(0.30,0.345,0.14,hexc('#D9732C'),-0.001)                                    # cuirass + sash
        slab(0.47,0.53,0.19,hexc('#E6B23E'),-0.001)                                                               # pauldrons
        slab(0.53,0.62,0.075,hexc('#F2C9A0'),-0.002); slab(0.585,0.625,0.085,hexc('#9A6533'),-0.003)               # head + hair
    return Q
names = list(d.keys())
sheet = Image.new("RGB",(150+5*W, len(names)*H),(255,255,255)); dr = ImageDraw.Draw(sheet)
for r,name in enumerate(names):
    fx = d[name]; dr.text((6, r*H+H//2-10), name, fill=(0,0,0)); dr.text((6, r*H+H//2+6), f"{fx['dur']} s", fill=(90,90,90))
    for c,fr in enumerate(fx["frames"]):
        im = (render_ruth if fx.get("scene") in ("ruth","daniel","exodus","prodigal","gabriel") else render)(fx, fr); ImageDraw.Draw(im).text((4,4), f"t={fr['t']:.2f}", fill=(60,60,60))
        sheet.paste(im,(150+c*W, r*H))
sheet.save(f"{out}/fx_contact.png"); print("ok", sheet.size)
