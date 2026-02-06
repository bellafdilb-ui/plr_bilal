"""
pdf_generator.py
================
Générateur PDF (Version Compacte : Optimisé pour 1 page).
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from io import BytesIO
import matplotlib.pyplot as plt

class PDFGenerator:
    def __init__(self, filename):
        self.filename = filename
        # MARGES RÉDUITES (1cm au lieu de 1.5cm)
        self.doc = SimpleDocTemplate(filename, pagesize=A4,
                                     rightMargin=1.0*cm, leftMargin=1.0*cm,
                                     topMargin=1.0*cm, bottomMargin=1.0*cm)
        self.elements = []
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        # Police titre un peu plus petite (14 vs 16)
        self.styles.add(ParagraphStyle(name='Header1', parent=self.styles['Heading1'], fontSize=14, spaceAfter=5, textColor=colors.darkblue))
        self.styles.add(ParagraphStyle(name='InfoLabel', parent=self.styles['Normal'], fontSize=10, fontName='Helvetica-Bold'))
        self.styles.add(ParagraphStyle(name='InfoValue', parent=self.styles['Normal'], fontSize=10))

    def generate(self, clinic_info, patient_info, exam_info, results, comments, graph_fig):
        # 1. EN-TÊTE CLINIQUE
        data_header = []
        
        logo_img = None
        if clinic_info.get('logo_path'):
            try:
                # Logo un peu plus petit (2.5cm)
                logo_img = Image(clinic_info['logo_path'], width=2.5*cm, height=2.5*cm, kind='proportional')
            except: pass
            
        txt_clinic = f"""
        <b>{clinic_info.get('name', 'Clinique Vétérinaire')}</b><br/>
        {clinic_info.get('address', '')}<br/>
        Tel: {clinic_info.get('phone', '')}<br/>
        <br/>
        <b>Praticien: {clinic_info.get('doctor_name', '')}</b>
        """
        
        if logo_img:
            data_header = [[logo_img, Paragraph(txt_clinic, self.styles['Normal'])]]
        else:
            data_header = [[Paragraph(txt_clinic, self.styles['Normal'])]]
            
        tbl_header = Table(data_header, colWidths=[3.5*cm, 12*cm])
        tbl_header.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
        self.elements.append(tbl_header)
        
        # Espace réduit (0.5cm)
        self.elements.append(Spacer(1, 0.5*cm))
        
        # 2. TITRE EXAMEN
        lat_text = "Oeil Droit (OD)" if exam_info.get('laterality') == 'OD' else "Oeil Gauche (OG)"
        title = f"Rapport PLR - {lat_text} - {exam_info.get('date', '')}"
        self.elements.append(Paragraph(title, self.styles['Header1']))
        self.elements.append(Spacer(1, 0.2*cm))
        
        # 3. INFOS PATIENT
        p_data = [
            [Paragraph("<b>Patient:</b>", self.styles['Normal']), patient_info.get('name')],
            [Paragraph("<b>Espèce/Race:</b>", self.styles['Normal']), f"{patient_info.get('species')} / {patient_info.get('breed')}"],
            [Paragraph("<b>ID / Puce:</b>", self.styles['Normal']), patient_info.get('id')],
            [Paragraph("<b>Propriétaire:</b>", self.styles['Normal']), patient_info.get('owner', '')]
        ]
        t_pat = Table(p_data, colWidths=[4*cm, 12*cm])
        t_pat.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 2),    # Padding réduit
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        self.elements.append(t_pat)
        self.elements.append(Spacer(1, 0.5*cm))
        
        # 4. GRAPHIQUE (Optimisé)
        img_buffer = BytesIO()
        # On réduit la hauteur à 7.5cm (au lieu de 10cm) pour gagner de la place
        graph_fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
        img_buffer.seek(0)
        im = Image(img_buffer, width=17*cm, height=7.5*cm) 
        self.elements.append(im)
        self.elements.append(Spacer(1, 0.3*cm))
        
        # 5. TABLEAU RÉSULTATS
        metrics_map = [
            ("baseline_mm", "Diamètre Basal"),
            ("min_diameter_mm", "Diamètre Minimal"),
            ("amplitude_mm", "Amplitude"),
            ("constriction_percent", "% Constriction"),
            ("constriction_velocity_mm_s", "Vitesse Max (mm/s)"),
            ("constriction_duration_s", "Durée Constriction (s)"),
            ("T75_recovery_s", "T75 Récupération (s)"),
            ("total_duration_s", "Durée Totale (s)"),
            ("flash_intensity_percent", "Intensité Flash (%)")
        ]

        # On fait un tableau plus large mais moins haut (2 colonnes de données ?)
        # Non, restons simple : Liste verticale mais compacte
        res_data = [["Paramètre Clinique", "Valeur"]]
        
        if results:
            for key, label in metrics_map:
                if key in results:
                    val = results[key]
                    val_str = str(val) if val is not None else "-"
                    if key in ["constriction_percent", "flash_intensity_percent"]: val_str += " %"
                    elif "mm" in key and "velocity" not in key: val_str += " mm"
                    res_data.append([label, val_str])
        
        t_res = Table(res_data, colWidths=[8*cm, 4*cm])
        t_res.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (1,0), colors.darkblue),
            ('TEXTCOLOR', (0,0), (1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('ALIGN', (0,0), (0,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('FONTNAME', (0,0), (1,0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
            ('TOPPADDING', (0,0), (-1,-1), 3),    # Lignes plus fines
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        self.elements.append(t_res)
        self.elements.append(Spacer(1, 0.5*cm))
        
        # 6. COMMENTAIRES
        if comments and comments.strip():
            self.elements.append(Paragraph("<b>Observations & Conclusions :</b>", self.styles['Heading3']))
            data_com = [[Paragraph(comments.replace('\n', '<br/>'), self.styles['Normal'])]]
            t_com = Table(data_com, colWidths=[17*cm]) # Prend toute la largeur
            t_com.setStyle(TableStyle([
                ('BOX', (0,0), (-1,-1), 1, colors.grey),
                ('BACKGROUND', (0,0), (-1,-1), colors.aliceblue),
                ('LEFTPADDING', (0,0), (-1,-1), 5),
                ('RIGHTPADDING', (0,0), (-1,-1), 5),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ]))
            self.elements.append(t_com)
        
        # Génération
        self.doc.build(self.elements)