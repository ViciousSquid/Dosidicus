import datetime
from PyQt5 import QtCore, QtGui, QtWidgets

class SquidCertificateWindow(QtWidgets.QDialog):
    def __init__(self, parent=None, tamagotchi_logic=None):
        super().__init__(parent)
        self.tamagotchi_logic = tamagotchi_logic
        self.setWindowTitle("Squid Certificate")
        self.setMinimumSize(800, 1000)  # Increased minimum size
        
        layout = QtWidgets.QVBoxLayout(self)
        
        self.certificate_view = QtWidgets.QTextBrowser()
        self.certificate_view.setOpenExternalLinks(False)
        layout.addWidget(self.certificate_view)
        
        # Add print button with larger text
        print_button = QtWidgets.QPushButton("Print Certificate")
        print_button.setStyleSheet("font-size: 18px; padding: 10px;")
        print_button.clicked.connect(self.print_certificate)
        layout.addWidget(print_button, alignment=QtCore.Qt.AlignRight)
        
        self.update_certificate()
    
    def update_certificate(self):
        if not self.tamagotchi_logic or not self.tamagotchi_logic.squid:
            return
            
        squid = self.tamagotchi_logic.squid
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        personality = str(squid.personality).split('.')[-1].lower().capitalize()
        squid_name = getattr(squid, 'name', 'Squid')
        
        certificate_html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Times New Roman', Times, serif;
                    margin: 0;
                    padding: 0;
                    background-color: #f9f7e8;
                    color: #333;
                }}
                .certificate {{
                    width: 100%;
                    max-width: 900px;
                    margin: 0 auto;
                    padding: 40px;
                    border: 25px solid #a28e5c;
                    background-color: #fff;
                    box-shadow: 0 0 15px rgba(0,0,0,0.3);
                    position: relative;
                    overflow: hidden;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    border-bottom: 3px solid #a28e5c;
                    padding-bottom: 20px;
                }}
                .title {{
                    font-size: 52px;  /* Increased from 42px */
                    font-weight: bold;
                    color: #7a693a;
                    text-transform: uppercase;
                    letter-spacing: 3px;
                    margin: 0;
                    line-height: 1.2;
                }}
                .subtitle {{
                    font-size: 28px;  /* Increased from 22px */
                    color: #666;
                    margin: 10px 0 0;
                }}
                .content {{
                    text-align: center;
                    margin: 30px 0;
                    font-size: 26px;  /* Increased from 20px */
                    line-height: 1.5;
                }}
                .name {{
                    font-size: 64px;  /* Increased from 50px */
                    font-family: 'Brush Script MT', cursive;
                    color: #333;
                    margin: 20px 0;
                    text-decoration: underline;
                    text-decoration-color: #a28e5c;
                    text-decoration-thickness: 2px;
                }}
                .stats {{
                    margin: 30px 0;
                    text-align: left;
                    font-size: 24px;  /* Increased from 18px */
                    line-height: 1.6;
                }}
                .stats h2 {{
                    font-size: 36px;  /* Increased from 30px */
                    color: #7a693a;
                    border-bottom: 2px solid #e2d9bc;
                    padding-bottom: 8px;
                }}
                .stats table {{
                    font-size: 26px;  /* Increased from 20px */
                    width: 100%;
                    margin: 20px 0;
                }}
                .stats table td {{
                    padding: 12px 0;
                }}
                .stats ul {{
                    font-size: 26px;  /* Increased from 20px */
                    padding-left: 30px;
                }}
                .stats li {{
                    margin-bottom: 15px;
                }}
                .seal {{
                    width: 150px;  /* Increased from 120px */
                    height: 150px;  /* Increased from 120px */
                    border-radius: 50%;
                    background-color: #e2d9bc;
                    border: 3px solid #7a693a;
                    margin: 0 auto;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: bold;
                    font-size: 32px;  /* Increased from 24px */
                    color: #7a693a;
                    transform: rotate(-15deg);
                    position: relative;
                    margin-top: 30px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                }}
                .date {{
                    font-size: 28px;  /* Increased from 22px */
                    font-style: italic;
                    margin-top: 40px;
                }}
                .personality {{
                    font-size: 36px;  /* New style for personality */
                    font-weight: bold;
                    color: #7a693a;
                    margin: 20px 0;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                }}
            </style>
        </head>
        <body>
            <div class="certificate">
                <div class="header">
                    <h1 class="title">Certificate of Squidship</h1>
                    <p class="subtitle">Presented by the International Dosidicus Society</p>
                </div>
                
                <div class="content">
                    <p>This certifies that</p>
                    <p class="name">{squid_name}</p>
                    <p>is an officially recognized Dosidicus electronicae of the</p>
                    <p class="personality">{personality} Personality Type</p>
                </div>
                
                <div class="stats">
                    <h2>Statistics</h2>
                    <table>
                        <tr>
                            <td><b>Happiness:</b> {squid.happiness}/100</td>
                            <td><b>Hunger:</b> {squid.hunger}/100</td>
                        </tr>
                        <tr>
                            <td><b>Cleanliness:</b> {squid.cleanliness}/100</td>
                            <td><b>Sleepiness:</b> {squid.sleepiness}/100</td>
                        </tr>
                        <tr>
                            <td><b>Anxiety:</b> {squid.anxiety}/100</td>
                            <td><b>Curiosity:</b> {squid.curiosity}/100</td>
                        </tr>
                    </table>
                </div>
                
                <div class="stats">
                    <h2>Achievements:</h2>
                    <ul>
                        <li>Successfully hatched a squid</li>
                        <li>Fed the squid over 10 times</li>
                        <li>Reached a happiness level above 80</li>
                        <li>Survived a difficult situation</li>
                    </ul>
                </div>
                
                <div style="text-align: center;">
                    <p class="date">Issued on this day, {current_date}</p>
                    <div class="seal">OFFICIAL</div>
                </div>
            </div>
        </body>
        </html>
        """
        
        self.certificate_view.setHtml(certificate_html)
    
    def print_certificate(self):
        from PyQt5 import QtPrintSupport
        printer = QtPrintSupport.QPrinter(QtPrintSupport.QPrinter.HighResolution)
        dialog = QtPrintSupport.QPrintDialog(printer, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.certificate_view.print_(printer)