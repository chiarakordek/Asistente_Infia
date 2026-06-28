from fpdf import FPDF

AREAS = [
    'IDENTIDAD Y CONVIVENCIA',
    'LENGUAJE Y LITERATURA',
    'MATEMÁTICAS',
    'CIENCIAS SOCIALES, CIENCIAS NATURALES Y TECNOLOGIA',
]

def es_area(linea):
    u = linea.upper().rstrip(':').strip()
    return u in AREAS or 'INFORME 2025' in u or linea.strip() == 'INFORMES EVALUATIVOS' or linea.strip().startswith('FALTAS:')

def informe_to_pdf(contenido, nombre_completo):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    for line in contenido.split('\n'):
        stripped = line.strip()
        if not stripped:
            pdf.ln(4)
            continue

        upper = stripped.upper().rstrip(':').strip()

        if stripped == 'INFORMES EVALUATIVOS':
            pdf.set_font('Helvetica', 'B', 16)
            pdf.cell(0, 10, stripped, ln=True, align='C')
        elif 'INFORME 2025' in stripped.upper():
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, stripped, ln=True, align='C')
        elif stripped.startswith('Sala:'):
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(0, 7, stripped, ln=True, align='C')
        elif upper in AREAS:
            pdf.set_font('Helvetica', 'B', 11)
            pdf.cell(0, 8, stripped, ln=True)
        elif stripped.upper().startswith('FALTAS'):
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(0, 8, stripped, ln=True)
        else:
            pdf.set_font('Helvetica', '', 10)
            pdf.multi_cell(0, 5.5, stripped)

    return pdf.output(dest='S').encode('latin-1', 'replace')
