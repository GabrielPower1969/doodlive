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
names = list(d.keys())
sheet = Image.new("RGB",(150+5*W, len(names)*H),(255,255,255)); dr = ImageDraw.Draw(sheet)
for r,name in enumerate(names):
    fx = d[name]; dr.text((6, r*H+H//2-10), name, fill=(0,0,0)); dr.text((6, r*H+H//2+6), f"{fx['dur']} s", fill=(90,90,90))
    for c,fr in enumerate(fx["frames"]):
        im = render(fx, fr); ImageDraw.Draw(im).text((4,4), f"t={fr['t']:.2f}", fill=(60,60,60))
        sheet.paste(im,(150+c*W, r*H))
sheet.save(f"{out}/fx_contact.png"); print("ok", sheet.size)
