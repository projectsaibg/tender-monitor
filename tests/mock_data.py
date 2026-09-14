"""Mock tender HTML pages for offline scraper/scan tests.

No test depends on a live website; these strings simulate portal responses.
LISTING_V1 is the baseline; LISTING_V2 adds a new tender (T-004) and changes
the closing date and value of T-002 (to exercise UPDATED detection).
"""

_TABLE = """
<html><body><h1>e-Tenders</h1>
<table>
<thead><tr>
  <th>Tender ID</th><th>Reference</th><th>Title</th><th>Organisation</th>
  <th>Location</th><th>Published Date</th><th>Closing Date</th>
  <th>Estimated Value</th><th>EMD</th>
</tr></thead>
<tbody>
%s
</tbody></table>
</body></html>
"""

_ROW = ("<tr><td>{tid}</td><td>{ref}</td>"
        "<td><a href=\"/tender/{tid}\">{title}</a>{doc}</td>"
        "<td>{org}</td><td>{loc}</td><td>{pub}</td><td>{close}</td>"
        "<td>{value}</td><td>{emd}</td></tr>")

_DOC = " <a href=\"/docs/{tid}_nit.pdf\">NIT</a>"


def _row(tid, ref, title, org, loc, pub, close, value, emd, doc=False):
    return _ROW.format(tid=tid, ref=ref, title=title, org=org, loc=loc, pub=pub,
                       close=close, value=value, emd=emd,
                       doc=_DOC.format(tid=tid) if doc else "")


LISTING_V1 = _TABLE % "\n".join([
    _row("T-001", "R/001", "Water pipeline supply work", "PHED", "Jaipur",
         "01 September 2026", "20 September 2026", "Rs. 15,00,000", "Rs. 30,000", doc=True),
    _row("T-002", "R/002", "STP sewerage treatment", "Municipal Corp", "Kota",
         "02 September 2026", "22 September 2026", "Rs. 5 Lakh", "Rs. 10,000"),
    _row("T-003", "R/003", "Vehicle hire for office", "PWD", "Ajmer",
         "03 September 2026", "25 September 2026", "Rs. 2,00,000", "Rs. 5,000"),
])

LISTING_V2 = _TABLE % "\n".join([
    _row("T-001", "R/001", "Water pipeline supply work", "PHED", "Jaipur",
         "01 September 2026", "20 September 2026", "Rs. 15,00,000", "Rs. 30,000", doc=True),
    _row("T-002", "R/002", "STP sewerage treatment", "Municipal Corp", "Kota",
         "02 September 2026", "27 September 2026", "Rs. 8 Lakh", "Rs. 10,000"),
    _row("T-003", "R/003", "Vehicle hire for office", "PWD", "Ajmer",
         "03 September 2026", "25 September 2026", "Rs. 2,00,000", "Rs. 5,000"),
    _row("T-004", "R/004", "WTP water treatment plant JJM", "Jal Jeevan Mission", "Udaipur",
         "10 September 2026", "30 September 2026", "Rs. 1.5 Crore", "Rs. 2,00,000", doc=True),
])

CARDS_V1 = """
<html><body>
<div class="tender-card"><h3>Water supply scheme</h3>
  <p>Tender ID: C-001</p><p>Organisation: PHED</p>
  <p>Closing Date: 2026-10-05</p><a href="/d/c1.pdf">Download</a></div>
<div class="tender-card"><h3>Sewerage STP project</h3>
  <p>Tender ID: C-002</p><p>Organisation: Municipal</p>
  <p>Closing Date: 2026-10-10</p><a href="/d/c2.pdf">Download</a></div>
<div class="tender-card"><h3>Pipeline JJM work</h3>
  <p>Tender ID: C-003</p><p>Organisation: Jal Board</p>
  <p>Closing Date: 2026-10-12</p><a href="/d/c3.pdf">Download</a></div>
</body></html>
"""

CAPTCHA_PAGE = """<html><body><form><div class="g-recaptcha" data-sitekey="x"></div>
<p>Please verify you are human</p></form></body></html>"""

LOGIN_PAGE = """<html><body><form action="/login">
<input name="username"><input type="password" name="password">
<button>Sign in</button></form></body></html>"""

PAGE_1 = """<html><body><table><thead><tr><th>Tender ID</th><th>Title</th><th>Closing Date</th></tr></thead>
<tbody><tr><td>P-001</td><td>Water page one</td><td>2026-09-20</td></tr></tbody></table>
<a href="/list?page=2" rel="next">Next</a></body></html>"""

PAGE_2 = """<html><body><table><thead><tr><th>Tender ID</th><th>Title</th><th>Closing Date</th></tr></thead>
<tbody><tr><td>P-002</td><td>Water page two</td><td>2026-09-21</td></tr></tbody></table>
</body></html>"""


# NIC eProcurement (GePNIC) style: a data table with <td> header cells (no
# <thead>/<th>), nested inside a layout table, with a combined
# "Title and Ref.No./Tender ID" column and "||"-separated organisation chain.
NIC_LISTING = """
<html><body>
<table><tr><td>
  <table>
    <tr>
      <td class="list_header">S.No</td>
      <td class="list_header">e-Published Date</td>
      <td class="list_header">Closing Date</td>
      <td class="list_header">Opening Date</td>
      <td class="list_header">Title and Ref.No./Tender ID</td>
      <td class="list_header">Organisation Chain</td>
    </tr>
    <tr>
      <td>1</td><td>11-Sep-2026 10:30 AM</td><td>29-Sep-2026 03:00 PM</td><td>30-Sep-2026 10:30 AM</td>
      <td>[Supply of Laboratory Equipments] [No.1-2(2)/2026-27/3494][2026_DAHV_31788_1]</td>
      <td>DEPARTMENT OF ANIMAL HUSBANDRY||HEAD OFFICE||Technical Section - II</td>
    </tr>
    <tr>
      <td>2</td><td>12-Sep-2026 09:00 AM</td><td>28-Sep-2026 03:00 PM</td><td>29-Sep-2026 10:30 AM</td>
      <td>[Replacement of 400mm CI conveying main] [PWD/DIV/13/2026][2026_DDW_31843_1]</td>
      <td>DEPARTMENT OF DRINKING WATER||CIRCLE - I||DIVISION XVI</td>
    </tr>
  </table>
</td></tr></table>
</body></html>
"""
