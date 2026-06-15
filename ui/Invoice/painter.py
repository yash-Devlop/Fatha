from __future__ import annotations
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtGui import (
    QPainter, QFont, QPen, QColor, QPageLayout, QPageSize,
    QFontMetrics)
from PySide6.QtCore import Qt, QRectF, QMarginsF, QLineF

MM = None

def _px(mm: float) -> float:
    return mm * MM

def _text_dynamic(painter, x, y, w, text, font, align):
    painter.setFont(font)
    rect = QRectF(x, y, w, 1000)
    bounding = painter.boundingRect(rect, Qt.TextFlag.TextWordWrap, text)
    h = bounding.height()
    painter.drawText(QRectF(x, y, w, h), Qt.TextFlag.TextWordWrap | align, text)
    return h

def _font(pt: float, bold=False, italic=False) -> QFont:
    pt = max(float(pt), 4.0)
    f  = QFont("Arial")
    f.setPointSizeF(pt)
    f.setBold(bold)
    f.setItalic(italic)
    return f

def _hline(p, x1_mm, y_mm, x2_mm):
    p.drawLine(QLineF(_px(x1_mm), _px(y_mm), _px(x2_mm), _px(y_mm)))

def _vline(p, x_mm, y1_mm, y2_mm):
    p.drawLine(QLineF(_px(x_mm), _px(y1_mm), _px(x_mm), _px(y2_mm)))

def _rect(p, x_mm, y_mm, w_mm, h_mm):
    p.drawRect(QRectF(_px(x_mm), _px(y_mm), _px(w_mm), _px(h_mm)))

def _fill(p, x_mm, y_mm, w_mm, h_mm, color):
    p.fillRect(QRectF(_px(x_mm), _px(y_mm), _px(w_mm), _px(h_mm)), QColor(color))

def _text(p, x_mm, y_mm, w_mm, h_mm, txt, font,
          align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
          pl=1.5, pr=1.5):
    txt = str(txt)
    if not txt:
        return
    x_inner = x_mm + pl
    w_inner = w_mm - pl - pr
    p.save()
    p.setFont(font)
    h_align = align & ~(
        Qt.AlignmentFlag.AlignVCenter |
        Qt.AlignmentFlag.AlignTop     |
        Qt.AlignmentFlag.AlignBottom
    )
    wrap_flag = Qt.TextFlag.TextWordWrap | h_align
    measure_rect = QRectF(_px(x_inner), _px(y_mm), _px(w_inner), _px(10000))
    bounding = p.boundingRect(measure_rect, wrap_flag, txt)
    natural_h_px = bounding.height()
    draw_h_px = max(_px(h_mm), natural_h_px)
    v_offset_px = 0.0
    if (align & Qt.AlignmentFlag.AlignVCenter) and natural_h_px <= _px(h_mm):
        v_offset_px = (_px(h_mm) - natural_h_px) / 2.0
    draw_rect = QRectF(
        _px(x_inner), _px(y_mm) + v_offset_px,
        _px(w_inner), draw_h_px,
    )
    p.setClipRect(QRectF(_px(x_mm), _px(y_mm), _px(w_mm), max(_px(h_mm), draw_h_px)))
    p.drawText(draw_rect, wrap_flag, txt)
    p.restore()

def _wrap(text: str, font: QFont, max_w_mm: float) -> list[str]:
    fm     = QFontMetrics(font)
    max_px = _px(max_w_mm)
    words  = str(text).split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if fm.horizontalAdvance(test) <= max_px:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines or [""]

def _str(v) -> str:
    return str(v) if v is not None else ""

def _draw_draft_watermark(p: QPainter, page_w_mm: float, page_h_mm: float):
    p.save()
    p.setPen(QColor(180, 180, 180))
    font = QFont("Arial")
    font.setPointSizeF(90)
    font.setBold(True)
    p.setFont(font)
    p.setOpacity(0.15)
    cx = _px(page_w_mm / 2)
    cy = _px(page_h_mm / 2)
    p.translate(cx, cy)
    p.rotate(-45)
    r = QRectF(_px(-100), _px(-25), _px(200), _px(50))
    p.drawText(r, Qt.AlignmentFlag.AlignCenter, "DRAFT")
    p.restore()


def draw_invoice(data: dict, file_path: str, draft: bool = False, performa: bool = False) -> bool:
    global MM
    if not performa:
        performa = "performa_no" in data.keys()
    try:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageLayout(QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            QMarginsF(0, 0, 0, 0),
            QPageLayout.Unit.Millimeter,
        ))

        pr_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
        MM = pr_rect.width() / 210.0
        if MM < 1:
            MM = 300.0 / 25.4

        p = QPainter()
        if not p.begin(printer):
            return False

        fCO  = _font(20,   bold=True)
        fTTL = _font(15,   bold=True)
        fLBL = _font(8.5, bold=True)
        fVAL = _font(9.5)
        fSMB = _font(9.0,  bold=True)
        fSM  = _font(8.5)
        fHDR = _font(9.0,  bold=True)
        fITM = _font(9.5)
        fSRN = _font(8.0,  italic=True)
        fGRD = _font(11.0, bold=True)
        fWRD = _font(8.5,  italic=True)

        thick = QPen(QColor("#000")); thick.setWidthF(_px(0.35))
        thin  = QPen(QColor("#000")); thin.setWidthF(_px(0.18))

        ML = 14.0; MT = 8.0; MR = 14.0
        PW = 210.0; PH = 297.0
        IW = PW - ML - MR
        RX = ML + IW
        PAGE_BOT = PH - MT

        RH  = 6.0
        RH2 = 5.5

        d       = {k: _str(v) for k, v in data.items() if not isinstance(v, (list, dict))}
        d["rows"] = data.get("rows", [])
        rows      = d["rows"]

        supply = d.get("supply_type", "within")
        if supply == "within":
            cgst_p, sgst_p, igst_p = "9%", "9%", "0%"
            igst_v = "0.00"
        else:
            cgst_p, sgst_p, igst_p = "0%", "0%", "18%"
            igst_v = d.get("igst", "0.00")

        BLW = IW * 0.55
        BRW = IW - BLW

        words_lines = _wrap(d.get("amount_words", "") + " Only", fWRD, BLW - 6)

        terms = [
            "(1) Our risk and responsibility ceases the moment goods are despatched.",
            "(2) Interest @ 21% P.A. will be charged if not paid within due date.",
            "(3) All matters are subject to Faridabad Jurisdiction.",
            "(4) E. & O.E.",
        ]
        terms_lines: list[str] = []
        for t in terms:
            terms_lines.extend(_wrap(t, fSM, BLW - 6))

        # ── column geometry ───────────────────────────────────────────
        ICOLS = [
            (["S.", "No."],              0.04, "c"),
            (["Product Description"],    0.38, "l"),
            (["HSN", "Code"],            0.08, "c"),
            (["Qty.", "(Set)"],          0.09, "c"),
            (["Rate", "(Rs)"],           0.10, "c"),
            (["Dis-", "count", "%"],     0.07, "c"),
            (["Taxable", "Amount (Rs)"], 0.24, "r"),
        ]
        col_x: list[float] = []
        cx_ = ML
        for _, frac, _ in ICOLS:
            col_x.append(cx_)
            cx_ += IW * frac
        col_x.append(RX)

        SKIP_VLINE_COLS = {1}

        IH_H       = 11.0
        item_rh_min = 6.5
        TOT_ROW_H  = 6.0
        SRN_GAP    = 1.2
        SRN_PAD_T  = 0.8

        aligns = [
            Qt.AlignmentFlag.AlignHCenter,
            Qt.AlignmentFlag.AlignLeft,
            Qt.AlignmentFlag.AlignHCenter,
            Qt.AlignmentFlag.AlignHCenter,
            Qt.AlignmentFlag.AlignRight,
            Qt.AlignmentFlag.AlignHCenter,
            Qt.AlignmentFlag.AlignRight,
        ]

        right_bot_h = (4 * RH2) + 7.5 + RH2 + RH2 + 12.0 + RH2
        left_bot_h = (
            RH2
            + len(words_lines) * RH2
            + 1.0
            + RH2
            + RH2
            + 1.0
            + RH2
            + len(terms_lines) * RH2
        )
        BOT_H = max(right_bot_h, left_bot_h) + 2.0

        def _measure_item_row(row_vals: list, serial_no_text: str) -> float:
            max_h = item_rh_min
            for i, val in enumerate(row_vals):
                if not val:
                    continue
                cw = col_x[i+1] - col_x[i]
                inner_w = cw - 3.0
                if inner_w <= 0:
                    continue
                p.setFont(fITM)
                bnd = p.boundingRect(
                    QRectF(0, 0, _px(inner_w), _px(10000)),
                    Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft,
                    str(val),
                )
                h_mm = bnd.height() / MM
                if i == 1 and serial_no_text:
                    p.setFont(fSRN)
                    sb = p.boundingRect(
                        QRectF(0, 0, _px(inner_w), _px(10000)),
                        Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft,
                        serial_no_text,
                    )
                    h_mm += sb.height() / MM + SRN_GAP + SRN_PAD_T
                if h_mm > max_h:
                    max_h = h_mm
            return max_h + 2.0

        processed_rows: list[dict] = []
        for ri, row in enumerate(rows):
            desc      = _str(row.get("description", ""))
            serial_no = _str(row.get("serial_no", "")).strip()
            qty_raw   = _str(row.get("qty", "")).strip()
            rate_s    = _str(row.get("rate", "")).strip()
            discount  = _str(row.get("discount", "")).strip()
            amount_s  = _str(row.get("amount", "")).strip()

            if not qty_raw:
                try:
                    rate_v = float(rate_s.replace(",", "")) if rate_s else 0.0
                    disc_v = float(
                        discount.replace("%","").replace(",","").strip() or "0"
                    ) if discount else 0.0
                    eff    = rate_v * (1.0 - disc_v / 100.0)
                    stored = float(amount_s.replace(",", "")) if amount_s else 0.0
                    if stored == 0.0 and eff > 0.0:
                        amount_s = f"{eff:,.2f}"
                except (ValueError, TypeError):
                    pass

            vals = [
                str(ri + 1), desc,
                _str(row.get("hsn", "")),
                qty_raw, rate_s,
                discount if discount else "",
                amount_s,
            ]
            processed_rows.append({
                "vals": vals,
                "serial_no": serial_no,
                "rh": _measure_item_row(vals, serial_no),
            })

        def draw_top_section(is_continuation: bool = False):
            cy = MT
            C1  = IW / 2
            CX2 = ML + C1

            p.setPen(thick)
            _hline(p, ML, cy, RX)

            name_h = 13.0
            _text(p, ML, cy, C1, name_h, d.get("company_name", ""),
                  fCO, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, pl=3)

            addr_lines = [x for x in [
                d.get("company_address", ""),
                ("M : " + d["company_mobile"]) if d.get("company_mobile") else "",
                ("E : " + d["company_email"])  if d.get("company_email")  else "",
            ] if x]

            sub_y = cy + name_h + 1.5
            LG_A  = 1.0
            tot_h = name_h
            for ln in addr_lines:
                h_px  = _text_dynamic(p, _px(ML+3), _px(sub_y), _px(C1-6), ln, fSM,
                                      Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                h_mm  = h_px / MM
                sub_y  += h_mm + LG_A
                tot_h  += h_mm + LG_A

            hdr_h = max(tot_h, 30.0)

            p.setPen(thick)
            _vline(p, CX2, cy, cy + hdr_h)

            copies = [
                (False, "Original for Recipient"),
                (False, "Duplicate for Transporter"),
                (False, "Triplicate for Supplier"),
                (False, "Extra Copy"),
            ]
            cb_y  = cy + 5.0
            row_w = 45.0
            for checked, label in copies:
                p.setPen(thin)
                sq = 3.0
                bx = RX - row_w
                by = cb_y + (RH2 - sq) / 2
                _rect(p, bx, by, sq, sq)
                if checked:
                    p.setFont(fSMB)
                    p.drawText(QRectF(_px(bx-.3), _px(by-.3), _px(sq+.6), _px(sq+.6)),
                               Qt.AlignmentFlag.AlignCenter, "✓")
                _text(p, bx+sq+2, cb_y, RX-(bx+sq+2), RH2, label, fSM,
                      Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, pl=0)
                cb_y += RH2

            p.setPen(thick)
            _hline(p, ML, cy + hdr_h, RX)

            # Title
            title = ("Proforma Invoice" if performa else "Tax Invoice") + (
                " (Continued)" if is_continuation else "")
            cy += hdr_h
            ttl_h = 9.0
            _text(p, ML, cy, IW, ttl_h, title,
                  fTTL, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            p.setPen(thick)
            _hline(p, ML, cy + ttl_h, RX)

            # Meta
            cy += ttl_h
            MC1 = IW * 0.37; MC2 = IW * 0.33; MC3 = IW - MC1 - MC2
            MX2 = ML + MC1;  MX3 = MX2 + MC2
            LBL_W_META = 28.0
            PAD_META   = 1.5

            inv_no_title = "Invoice No. :" if not performa else "Proforma No. :"
            inv_no = (d.get("invoice_no","") or "—") if not performa else d.get("performa_no","")
            inv_dt_title = "Invoice Date :" if not performa else "PI Date: "

            rows_L = [
                ("GSTIN :",          d.get("company_gstin","") or "—"),
                ("Transport Mode :", d.get("transport_mode","") or "—"),
                ("Destination :",    d.get("destination","")   or "—"),
                ("E-Way Bill No. :", d.get("eway","")          or "—"),
            ]
            rows_M = [
                (inv_no_title,        inv_no),
                ("P.O. No. :",        d.get("po_no","")    or "—"),
                ("State of Supply :", d.get("state","")    or "—"),
                ("", ""),
            ]
            rows_R = [
                (inv_dt_title,  d.get("bill_date","")  or "—"),
                ("Order Date :", d.get("order_date","") or "—"),
                ("State Code :", d.get("state_code","") or "—"),
                ("", ""),
            ]

            def draw_meta_col(sx, cw, mrows, lw):
                fy = cy + PAD_META
                for lbl, val in mrows:
                    if not lbl and not val:
                        fy += RH2; continue
                    p.save()
                    p.setFont(fLBL)
                    p.drawText(
                        QRectF(_px(sx + 2), _px(fy), _px(lw), _px(RH2)),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine,
                        lbl
                    )
                    p.restore()
                    h_px = _text_dynamic(p, _px(sx + lw), _px(fy), _px(cw - lw - 1), val, fVAL,
                                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                    fy += max(h_px/MM, RH2) + 1.0
                return fy - cy

            h_L = draw_meta_col(ML,  MC1, rows_L, LBL_W_META)
            h_M = draw_meta_col(MX2, MC2, rows_M, LBL_W_META)
            h_R = draw_meta_col(MX3, MC3, rows_R, 25.0)
            meta_h = max(h_L, h_M, h_R) + PAD_META

            p.setPen(thin)
            _vline(p, MX2, cy, cy + meta_h)
            _vline(p, MX3, cy, cy + meta_h)
            p.setPen(thick)
            _hline(p, ML, cy + meta_h, RX)

            cy += meta_h
            bh_h = 6.0
            HC = IW/2; HX = ML + HC
            p.setPen(thin)
            _vline(p, HX, cy, cy + bh_h)
            _text(p, ML, cy, HC, bh_h, "Billed to :",
                  fSMB, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            _text(p, HX, cy, HC, bh_h, "Shipped to :",
                  fSMB, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            p.setPen(thick)
            _hline(p, ML, cy + bh_h, RX)

            cy += bh_h
            HC = IW/2; HX = ML + HC
            PAD_P = 2.0; LBL_W_P = 28.0; LG_P = 1.2

            def _measure_party(dd, show_mobile=False):
                fy = PAD_P
                fm = QFontMetrics(fVAL)
                vwpx = _px(HC - LBL_W_P - PAD_P*2)

                rows = [
                    ("Name :",    dd["name"]),
                    ("Address :", dd["address"]),
                    ("GSTIN :",   dd["gstin"] or "—"),
                    ("State :",   f'{dd["state"]}   Code : {dd["scode"]}'),
                ]

                mobile = (dd.get("client_mobile") or "").strip()
                alt_mobile = (dd.get("client_alt_mobile") or "").strip()

                if show_mobile:
                    if mobile:
                        rows += [("Mobile :", mobile or "—")]
                    if alt_mobile:
                        rows += [("Alt Mobile :", alt_mobile or "—")]

                for lbl, val in rows:
                    val = (val or "").strip()

                    if not val and "Mobile" not in lbl:
                        continue

                    val = val or "—"

                    words = str(val).split()
                    lc = 1
                    cur = ""

                    for w in words:
                        t = (cur + " " + w).strip()
                        if fm.horizontalAdvance(t) <= vwpx:
                            cur = t
                        else:
                            if cur:
                                lc += 1
                            cur = w

                    fy += max(fm.height()/MM * lc, RH2) + LG_P

                return fy + PAD_P

            def draw_party(x, y, w, dd, show_mobile=False):
                fy = y + PAD_P

                rows = [
                    ("Name :",    dd["name"],    True),
                    ("Address :", dd["address"], False),
                    ("GSTIN :",   dd["gstin"] or "—", False),
                    ("State :",   f'{dd["state"]}   Code : {dd["scode"]}', False),
                ]

                if show_mobile:
                    rows += [
                        ("Mobile :", dd.get("client_mobile","") or "—", False),
                        ("Alt Mobile :", dd.get("client_alt_mobile","") or "—", False),
                    ]

                for lbl, val, bold in rows:
                    if not (val or "").strip() or (val or "").strip() == "—":
                        continue
                    _text(p, x+PAD_P, fy, LBL_W_P, RH2, lbl, fLBL,
                          Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                    h_px = _text_dynamic(p, _px(x+PAD_P+LBL_W_P), _px(fy),
                                         _px(w - LBL_W_P - PAD_P*2),
                                         val, fSMB if bold else fVAL,
                                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                    fy += h_px/MM + LG_P
                return fy - y + PAD_P

            ld = {
                "name":    d.get("client_name",""),
                "address": d.get("client_address",""),
                "gstin":   d.get("client_gstin",""),
                "state":   d.get("client_state", d.get("state","")),
                "scode":   d.get("client_state_code", d.get("state_code","")),
                "client_mobile": d.get("client_mobile",""),
                "client_alt_mobile": d.get("client_alt_mobile",""),
            }
            rd = {
                "name":    d.get("ship_name", d.get("client_name","")),
                "address": d.get("ship_address","---- SAME ----"),
                "gstin":   d.get("ship_gstin",""),
                "state":   d.get("ship_state", d.get("client_state", d.get("state",""))),
                "scode":   d.get("ship_state_code", d.get("client_state_code", d.get("state_code",""))),
            }
            ph = max(_measure_party(ld, show_mobile=True), _measure_party(rd))
            draw_party(ML, cy, HC, ld, show_mobile=True)
            draw_party(HX, cy, HC, rd)

            p.setPen(thin)
            _vline(p, HX, cy, cy + ph)
            p.setPen(thick)
            _hline(p, ML, cy + ph, RX)
            cy += ph
            return cy, MT

        def draw_items_header(cy: float) -> float:
            _fill(p, ML, cy, IW, IH_H, "#e8e8e8")
            p.setPen(thin)
            for i, (lines, _, al) in enumerate(ICOLS):
                cw = col_x[i+1] - col_x[i]
                flag = (Qt.AlignmentFlag.AlignHCenter if al=="c" else
                        Qt.AlignmentFlag.AlignRight   if al=="r" else
                        Qt.AlignmentFlag.AlignLeft)
                lh = IH_H / max(len(lines), 1)
                for j, ln in enumerate(lines):
                    _text(p, col_x[i], cy+j*lh, cw, lh, ln, fHDR,
                          flag | Qt.AlignmentFlag.AlignVCenter, pl=1.5, pr=1.5)
                if i not in SKIP_VLINE_COLS:
                    _vline(p, col_x[i], cy, cy + IH_H)
            _vline(p, RX, cy, cy + IH_H)
            p.setPen(thick)
            _hline(p, ML, cy, RX)
            _hline(p, ML, cy + IH_H, RX)
            return cy + IH_H

        def draw_item_row(cy: float, row_data: dict) -> float:
            vals      = row_data["vals"]
            serial_no = row_data["serial_no"]
            item_rh   = row_data["rh"]
            p.setPen(thin)
            for i, val in enumerate(vals):
                cw = col_x[i+1] - col_x[i]
                if i == 1:
                    _text(p, col_x[i], cy, cw, item_rh, val, fITM,
                          Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                          pl=1.5, pr=1.5)
                    if serial_no:
                        p.setFont(fITM)
                        inner_w = cw - 3.0
                        dm = p.boundingRect(
                            QRectF(0, 0, _px(inner_w), _px(10000)),
                            Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft, val)
                        srn_y = cy + dm.height()/MM + SRN_PAD_T
                        _text(p, col_x[i], srn_y, cw,
                              item_rh - dm.height()/MM - SRN_PAD_T,
                              serial_no, fSRN,
                              Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                              pl=1.5, pr=1.5)
                else:
                    _text(p, col_x[i], cy, cw, item_rh, val, fITM,
                          aligns[i] | Qt.AlignmentFlag.AlignVCenter, pl=1.5, pr=1.5)
                if i not in SKIP_VLINE_COLS:
                    _vline(p, col_x[i], cy, cy + item_rh)
            _vline(p, RX, cy, cy + item_rh)
            _hline(p, ML, cy + item_rh, RX)
            return cy + item_rh

        def draw_totals_row(cy: float) -> float:
            p.setPen(thick)
            _hline(p, ML, cy, RX)
            _text(p, ML, cy, col_x[3]-ML, TOT_ROW_H, "Total",
                  fSMB, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            p.setPen(thin)
            _vline(p, col_x[3], cy, cy + TOT_ROW_H)
            _text(p, col_x[3], cy, col_x[4]-col_x[3], TOT_ROW_H,
                  d.get("total_qty",""), fSMB,
                  Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            _vline(p, col_x[4], cy, cy + TOT_ROW_H)
            _vline(p, col_x[5], cy, cy + TOT_ROW_H)
            _vline(p, col_x[6], cy, cy + TOT_ROW_H)
            _text(p, col_x[6], cy, col_x[7]-col_x[6], TOT_ROW_H,
                  d.get("total_amount",""), fSMB,
                  Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, pr=2)
            _vline(p, RX, cy, cy + TOT_ROW_H)
            p.setPen(thick)
            _hline(p, ML, cy + TOT_ROW_H, RX)
            return cy + TOT_ROW_H

        def draw_bottom_section(bot_y: float, outer_top: float) -> None:
            """
            Draw bottom section starting at bot_y (= PAGE_BOT - BOT_H).
            Then draw the outer page border from outer_top to PAGE_BOT.
            """
            BRX = ML + BLW
            TLW = BRW * 0.56
            TPW = BRW * 0.16
            TVW = BRW - TLW - TPW

            rx_y = bot_y
            p.setPen(thin)
            for tlbl, tpct, tval in [
                ("Add : CGST @", cgst_p, d.get("cgst",  "0.00")),
                ("Add : SGST @", sgst_p, d.get("sgst",  "0.00")),
                ("Add : IGST @", igst_p, igst_v),
                ("R/off",        "",     d.get("roff",  "0.00")),
            ]:
                _text(p, BRX, rx_y, TLW, RH2, tlbl, fLBL,
                      Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, pl=3)
                if tpct:
                    _text(p, BRX+TLW, rx_y, TPW, RH2, tpct, fVAL,
                          Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, pr=1)
                _text(p, BRX+TLW+TPW, rx_y, TVW, RH2, tval, fVAL,
                      Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, pr=2)
                rx_y += RH2

            gt_h = 7.5
            p.setPen(thick)
            _hline(p, BRX, rx_y, RX)
            _fill(p, BRX, rx_y, BRW, gt_h, "#f0f0f0")
            _text(p, BRX, rx_y, TLW+TPW, gt_h, "Grand Total", fGRD,
                  Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, pl=3)
            _text(p, BRX+TLW+TPW, rx_y, TVW, gt_h, d.get("grand_total",""), fGRD,
                  Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, pr=2)
            _hline(p, BRX, rx_y + gt_h, RX)
            rx_y += gt_h

            _text(p, BRX, rx_y, BRW, RH2,
                  "Certified that the particulars given above are true & correct",
                  fSM, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, pl=2)
            rx_y += RH2
            _text(p, BRX, rx_y, BRW, RH2,
                  f"For {d.get('company_name','')}",
                  fSMB, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, pr=3)
            rx_y += RH2 + 12.0
            _text(p, BRX, rx_y, BRW, RH2, "(Auth. Signatory)",
                  fSMB, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, pr=3)

            # ── Left: words + bank + terms ────────────────────────────
            lx_y = bot_y
            _text(p, ML, lx_y, BLW, RH2,
                  "Total Invoice Amount (in words) :", fLBL,
                  Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, pl=2)
            lx_y += RH2

            for i, wl in enumerate(words_lines):
                if i == 0:
                    wl = "Indian Rupees " + wl
                _text(p, ML, lx_y, BLW, RH2, wl, fWRD,
                      Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, pl=3)
                lx_y += RH2
            lx_y += 1.0

            _text(p, ML, lx_y, 20, RH2, "BANK :", fLBL, pl=2)
            _text(p, ML+20, lx_y, BLW-22, RH2, d.get("bank_name","") or "—", fVAL, pl=0)
            lx_y += RH2

            _text(p, ML, lx_y, 20, RH2, "C/A No. :", fLBL, pl=2)
            ca = (_str(d.get("account","") or "—") +
                  "   IFS Code : " + _str(d.get("ifsc","") or "—"))
            _text(p, ML+20, lx_y, BLW-22, RH2, ca, fVAL, pl=0)
            lx_y += RH2 + 1.0

            _text(p, ML, lx_y, BLW, RH2, "Terms & Conditions :", fSMB, pl=2)
            lx_y += RH2
            for tl in terms_lines:
                _text(p, ML, lx_y, BLW, RH2, tl, fSM,
                      Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, pl=3)
                lx_y += RH2

            p.setPen(thick)
            _vline(p, BRX, bot_y, PAGE_BOT)

            _hline(p, ML, PAGE_BOT, RX)

            _rect(p, ML, outer_top, IW, PAGE_BOT - outer_top)

        cy, outer_top = draw_top_section(is_continuation=False)
        cy = draw_items_header(cy)
        items_start_y_p1 = cy

        avail_p1   = PAGE_BOT - items_start_y_p1 - TOT_ROW_H - BOT_H
        avail_cont = avail_p1

        pages_groups: list[list] = []
        cur_group: list = []
        cur_h = 0.0
        avail_cur = avail_p1

        for pr_row in processed_rows:
            rh = pr_row["rh"]
            if cur_h + rh > avail_cur and cur_group:
                pages_groups.append(cur_group)
                cur_group = []
                cur_h = 0.0
                avail_cur = avail_cont
            cur_group.append(pr_row)
            cur_h += rh

        if cur_group:
            pages_groups.append(cur_group)
        if not pages_groups:
            pages_groups = [[]]

        for page_idx, row_group in enumerate(pages_groups):
            is_last = page_idx == len(pages_groups) - 1

            if page_idx == 0:
                pass
            else:
                printer.newPage()
                cy, outer_top = draw_top_section(is_continuation=True)
                cy = draw_items_header(cy)

            for pr_row in row_group:
                cy = draw_item_row(cy, pr_row)

            if is_last:
                tot_row_y = PAGE_BOT - BOT_H - TOT_ROW_H

                remaining = tot_row_y - cy
                if remaining > 0:
                    n_blanks = max(1, int(remaining / item_rh_min))
                    blank_h  = remaining / n_blanks

                    p.setPen(thin)
                    for _ in range(n_blanks):
                        for i in range(len(ICOLS)):
                            if i not in SKIP_VLINE_COLS:
                                _vline(p, col_x[i], cy, cy + blank_h)
                        _vline(p, RX, cy, cy + blank_h)
                        cy += blank_h
                    p.setPen(thick)
                    _hline(p, ML, cy, RX)

                elif remaining < 0:
                    pass

                cy = tot_row_y
                draw_totals_row(cy)

                bot_y = PAGE_BOT - BOT_H
                draw_bottom_section(bot_y, outer_top)

            else:
                _fill(p, ML, cy, IW, RH2, "#f0f0f0")
                p.setPen(thin)
                _text(p, ML, cy, IW, RH2, "Continued on next page...", fSM,
                      Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
                p.setPen(thick)
                _hline(p, ML, cy + RH2, RX)
                cy += RH2
                _rect(p, ML, outer_top, IW, cy - outer_top)

            if draft:
                _draw_draft_watermark(p, PW, PH)

        p.end()
        return True

    except Exception:
        import traceback; traceback.print_exc()
        try: p.end()
        except: pass
        return False


# ── demo / standalone test ────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    sample_data = {
        "company_name":    "Sharma Electronics Pvt. Ltd.",
        "company_address": "Plot 42, Sector 25, Industrial Area, Faridabad – 121004, Haryana",
        "company_mobile":  "+91-98765-43210",
        "company_email":   "accounts@sharmaelectronics.in",
        "company_gstin":   "06AABCS1429B1ZB",

        "invoice_no":  "INV-2025-0842",
        "bill_date":   "25 Mar 2025",
        "order_date":  "20 Mar 2025",
        "po_no":       "PO-2025-1137",
        "state":       "Haryana",
        "state_code":  "06",
        "transport_mode": "Road",
        "destination": "Delhi",
        "eway":        "EWB-120034567812",
        "supply_type": "within",

        "client_name":       "Rajesh Kumar & Sons",
        "client_address":    "B-14, Nehru Place, New Delhi - 110019",
        "client_gstin":      "07AABCR1234C1ZD",
        "client_state":      "Delhi",
        "client_state_code": "07",

        "ship_name":         "Rajesh Kumar & Sons",
        "ship_address":      "Warehouse 3, Okhla Industrial Estate, Phase II, New Delhi - 110020",
        "ship_gstin":        "07AABCR1234C1ZD",
        "ship_state":        "Delhi",
        "ship_state_code":   "07",

        "rows": [
            {
                "description": "LED Panel Light 18W Square (Warm White) - High Efficiency Energy Saving Model",
                "serial_no":   "Sr. No: LP18W-0042 / LP18W-0043 / LP18W-0044 (batch Jan-2025)",
                "hsn": "940540", "qty": "50", "rate": "320.00", "discount": "5%",
                "amount": "15,200.00",
            },
            {
                "description": "Smart WiFi Switch 16A (2-Gang)",
                "hsn": "853650", "qty": "30", "rate": "450.00",
                "discount": "", "amount": "13,500.00",
            },
            {
                "description": "Copper Cable 4 Sq.mm - 90m Roll",
                "serial_no":   "Reel Nos: CR-2025-001 through CR-2025-010; ISI certified, tested per IS 694:2010",
                "hsn": "854411", "qty": "10", "rate": "1,750.00",
                "discount": "", "amount": "17,500.00",
            },
            {
                "description": "MCB 32A Single Pole (C-Curve) with surge protection rated for industrial environments",
                "serial_no":   "Lot: MCB-SRG-L22B",
                "hsn": "853620", "rate": "180.00", "discount": "10%", "amount": "3,240.00",
            },
            {
                "description": "Modular Socket 6A + 16A Combo",
                "hsn": "853669", "qty": "100", "rate": "95.00",
                "discount": "", "amount": "9,500.00",
            },
        ],

        "total_qty":    "190 Pcs",
        "total_amount": "58,940.00",
        "cgst":         "5,304.60",
        "sgst":         "5,304.60",
        "igst":         "0.00",
        "roff":         "-0.20",
        "grand_total":  "69,549.00",
        "amount_words": "Sixty Nine Thousand Five Hundred Forty Nine Rupees",

        "bank_name": "State Bank of India, Sector 16, Faridabad",
        "account":   "32104567891234",
        "ifsc":      "SBIN0001234",
    }

    ok = draw_invoice(sample_data, "/mnt/user-data/outputs/sample_invoice.pdf", draft=False)
    print("Generated:", ok)
