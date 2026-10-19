"""Render the English written submission using vector text/tables/flow diagram."""
import re
from html import escape
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
ROOT=Path(__file__).resolve().parents[1]
INK=HexColor('#153f35'); GREEN=HexColor('#1e6a50'); MUTED=HexColor('#617267'); LIGHT=HexColor('#edf3e7')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='Title2',fontName='Helvetica-Bold',fontSize=25,leading=29,textColor=INK,spaceAfter=12))
styles.add(ParagraphStyle(name='Sub',fontName='Helvetica',fontSize=13,leading=18,textColor=GREEN,spaceAfter=8))
styles.add(ParagraphStyle(name='H2x',fontName='Helvetica-Bold',fontSize=16,leading=20,textColor=INK,spaceBefore=12,spaceAfter=11,keepWithNext=True))
styles.add(ParagraphStyle(name='H3x',fontName='Helvetica-Bold',fontSize=10.5,leading=14,textColor=GREEN,spaceBefore=9,spaceAfter=5,keepWithNext=True))
styles.add(ParagraphStyle(name='Bodyx',fontName='Helvetica',fontSize=9,leading=12,textColor=INK,spaceAfter=6))
styles.add(ParagraphStyle(name='Cellx',fontName='Helvetica',fontSize=8,leading=11,textColor=INK))
styles.add(ParagraphStyle(name='Headx',fontName='Helvetica-Bold',fontSize=8,leading=11,textColor=white))
styles.add(ParagraphStyle(name='Bulletx',parent=styles['Bodyx'],leftIndent=10,firstLineIndent=-7,spaceAfter=5))
def inline(s):
    s=escape(s).replace('→','-&gt;').replace('−','-')
    s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'`([^`]+)`',r'<font name="Courier">\1</font>',s)
    return s

def diagram():
    d=Drawing(475,225)
    def box(x,y,w,h,title,subtitle='',draft=False):
        d.add(Rect(x,y,w,h,rx=5,fillColor=LIGHT if not draft else HexColor('#f8f6ed'),strokeColor=HexColor('#cad9c8'),strokeWidth=.7))
        d.add(String(x+w/2,y+h-17,title,fontName='Helvetica-Bold',fontSize=9,fillColor=INK,textAnchor='middle'))
        if subtitle:d.add(String(x+w/2,y+12,subtitle,fontName='Helvetica',fontSize=7.5,fillColor=MUTED,textAnchor='middle'))
    def arrow(x1,y1,x2,y2):
        d.add(Line(x1,y1,x2,y2,strokeColor=GREEN,strokeWidth=1))
        if x2>x1:d.add(Polygon([x2,y2,x2-5,y2+3,x2-5,y2-3],fillColor=GREEN,strokeColor=GREEN))
        elif x2<x1:d.add(Polygon([x2,y2,x2+5,y2+3,x2+5,y2-3],fillColor=GREEN,strokeColor=GREEN))
        elif y2<y1:d.add(Polygon([x2,y2,x2-3,y2+5,x2+3,y2+5],fillColor=GREEN,strokeColor=GREEN))
    box(0,169,140,48,'1. Acquire evidence','Upload / mock API pull');box(166,169,140,48,'2. Parse & validate','Coverage, rows, balances');box(332,169,140,48,'Correction queue','Blockers -> re-upload')
    arrow(140,193,166,193);arrow(306,193,332,193)
    box(166,87,140,48,'3. Reconcile & analyze','Rules + local anomaly flags');arrow(236,169,236,135)
    box(0,87,140,48,'4. Inspect evidence','Brief, ledger, hashes');arrow(166,111,140,111)
    box(0,5,140,48,'5. Approve version','Human + consent (design)',True);arrow(70,87,70,53)
    box(166,5,140,48,'6. Durable bank outbox','Idempotency key (design)',True);arrow(140,29,166,29)
    box(332,5,140,48,'7. Verify bank status','Confirm / escalate (design)',True);arrow(306,29,332,29)
    d.add(String(334,132,'Any data blocker prevents readiness.',fontName='Helvetica',fontSize=7,fillColor=MUTED))
    d.add(String(334,119,'Steps 1-4 are implemented locally.',fontName='Helvetica',fontSize=7,fillColor=MUTED))
    d.add(String(334,106,'Steps 5-7 are production design.',fontName='Helvetica',fontSize=7,fillColor=MUTED))
    return d

def footer(c,doc):
    w,h=doc.pagesize;c.saveState();c.setStrokeColor(HexColor('#dce5d9'));c.line(47,h-38,w-47,h-38)
    c.setFont('Helvetica-Bold',8);c.setFillColor(GREEN);c.drawString(47,h-29,'QAWAFEL / TECHNICAL ASSESSMENT')
    c.setFont('Helvetica',8);c.setFillColor(MUTED);c.drawRightString(w-47,h-29,'Abdulrahman Alrehaili')
    c.line(47,38,w-47,38);c.setFont('Helvetica',7);c.drawString(47,25,'Financing Evidence Workbench | Fictional data only | 19 Oct 2026');c.drawRightString(w-47,25,str(doc.page));c.restoreState()

def main():
    lines=(ROOT/'docs/submission.md').read_text().splitlines();story=[];i=0
    while i<len(lines):
        l=lines[i].strip()
        if not l:i+=1;continue
        if l=='[PAGE]':story.append(PageBreak());i+=1;continue
        if l=='[DIAGRAM]':story.extend([diagram(),Spacer(1,6)]);i+=1;continue
        if l.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+',x or '-') for x in cells):rows.append(cells)
                i+=1
            n=len(rows[0]); widths={2:[135,340],3:[94,170,211],4:[110,105,130,130]}.get(n,[475/n]*n)
            data=[[Paragraph(inline(v),styles['Headx' if r==0 else 'Cellx']) for v in row] for r,row in enumerate(rows)]
            t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),INK),('ROWBACKGROUNDS',(0,1),(-1,-1),[white,HexColor('#f5f8f1')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,0),.5,INK),('LINEBELOW',(0,1),(-1,-1),.25,HexColor('#dce6d7'))]));story.extend([t,Spacer(1,9)]);continue
        if l.startswith('# '):story.append(Paragraph(inline(l[2:]),styles['Title2']))
        elif l.startswith('## '):
            title=l[3:]
            if title.startswith(('Task 2','Task 4','Task 5')):story.append(PageBreak())
            story.append(Paragraph(inline(title),styles['Sub'] if title=='Financing Evidence Workbench' else styles['H2x']))
        elif l.startswith('### '):story.append(Paragraph(inline(l[4:]),styles['H3x']))
        else:
            bullet=l.startswith('- ');story.append(Paragraph(('• '+inline(l[2:])) if bullet else inline(l),styles['Bulletx'] if bullet else styles['Bodyx']))
        i+=1
    path=ROOT/'docs/Qawafel_Submission.pdf';SimpleDocTemplate(str(path),pagesize=(595.28,841.89),rightMargin=60,leftMargin=60,topMargin=53,bottomMargin=48,title='Qawafel Technical Assessment - Financing Evidence Workbench',author='Abdulrahman Alrehaili').build(story,onFirstPage=footer,onLaterPages=footer);print(path)
if __name__=='__main__':main()
