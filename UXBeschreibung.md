<!-- Seite 1 -->
Folgender Ablauf aus User Sicht:
Das Tool wird per Mausklick geöffnet (EXE).
Der User sieht
● Eine leere Tabelle, in der verschiedene Kisten erfasst werden können
● Einen Wartebereich, in dem erstelle Kisten grafisch dargestellt werden
● Diverse Buttons
● Den Bereich, in dem der Container angezeigt wird.

6 Buttons:
● Containerauswahl (20ft, 40ft, 40ft HC, 40ft OT)
● Kisten gestapelt erstellen (lt. Stapelregeln werden gestapelte Kisten erstellt)
● Kisten einzeln erstellen (Kisten werden nicht gestapelt erstellt)
● Projekt laden
● Projekt speichern
● Projekt abgeschlossen, Daten exportieren (es wird eine PDF oder ähnliches Dokument erstellt, das leicht geteilt werden kann)

Als erstes gibt der User den Kistennamen, die Kistenanzahl, Dimensionen (in mm) sowie das Gewicht (in kg) ein – entweder eine Kiste oder verschiedene. Jedem neu erstellten Kistentyp soll eine Farbe zugeordnet werden, die der User bei Bedarf ändern kann.

Danach entscheidet er, welchen Container er befüllen will, und wählt einen aus. Der Container soll dann als 2D‑Umriss erscheinen – und zwar maßstabsgetreu.

Anschließend wählt er, ob die Kisten einzeln oder gestapelt erstellt werden. Werden Kisten gestapelt erstellt, dürfen nur identische Kisten so oft gestapelt werden, dass die maximale Türöffnung des jeweiligen Containers nicht überschritten wird.

Es werden immer Grafiken für alle Kisten erstellt – exakt im Maßstab.

Im Wartebereich sieht er die erstellten Kisten als beschriftete Grafik. Jede Kiste trägt: Kistenname, Grundmaße, Menge und Gesamthöhe. Klickt er erneut auf »Erstellen«, werden alle vorhandenen Kisten (im Wartebereich und Container) gelöscht und neu erzeugt.

Nun beginnt die Planung der Containerbeladung.
• Der User muss Kisten manuell stapeln können, indem er eine Kiste auf eine andere bewegt.
 → Das Programm bildet dann einen Stapel (»Einheit«), die markierte Kiste liegt oben.
• Kisten / Stapel werden per Drag & Drop in den Container gezogen.
• Innerhalb des Containers kann der User Kisten neu platzieren; bei Bedarf auch zurück in den Wartebereich.
• Platziert er eine Kiste außerhalb des Containers oder oberhalb einer anderen Kiste/Stapel, färbt sie sich rot.

Ist die Planung fertig, klickt er auf »Projekt abgeschlossen, Daten exportieren«. Das Programm erzeugt ein Dokument (PDF o. Ä.), das leicht geteilt werden kann.

---

<!-- Seite 2 -->
Das Export‑Dokument enthält:
• 2D‑Draufsicht des Containers (inkl. Kistenbeschriftung)
• 2D‑Seitenansicht des Containers (inkl. Kistenbeschriftung)
• 3D‑Ansicht des beladenen Containers
• Tabelle mit allen verladenen Kisten (Name, Anzahl, Länge, Breite, Höhe, Gewicht)
• Tabelle mit nicht verladenen Kisten (Kisten im Wartebereich)

Danach kann der User:
• Das Projekt speichern.
• Ohne Speichern schließen.
• Ein neues Beladeprojekt starten (alle Eingaben werden gelöscht).

Beim Laden eines Projekts werden alle Kisten und ihre Platzierung wiederhergestellt; der User kann Kistentypen ergänzen und Kisten erneut generieren.

Technische Muss‑Kriterien:
• Container und Kisten immer maßstabsgetreu zeichnen.
• Kisten müssen zwischen Wartebereich und Container gezogen werden können.
• Prüfung, wenn Kisten über Containermaße hinausragen oder auf anderen Kisten liegen.
• Undo/Redo ist **nicht** notwendig.
• Zoom im Container und Wartebereich (identisches Verhalten, um Maßstab zu gewährleisten).
