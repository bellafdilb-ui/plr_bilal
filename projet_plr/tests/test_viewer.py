"""
tests/test_viewer.py
====================
Test du widget graphique PLRGraphWidget.
"""
import pytest
import pandas as pd
from plr_results_viewer import PLRGraphWidget, PLRResultsDialog

def test_graph_plotting(qtbot):
    """Vérifie que le widget peut tracer une courbe sans erreur."""
    widget = PLRGraphWidget()
    qtbot.addWidget(widget)
    
    # 1. Création de données fictives
    df = pd.DataFrame({
        'timestamp_s': [0.0, 0.5, 1.0],
        'diameter_mm': [5.0, 4.0, 5.0],
        'diameter_smooth': [5.0, 4.0, 5.0]
    })
    data = [{'label': 'Test', 'df': df, 'metrics': {}, 'color': 'blue'}]
    
    # 2. Affichage
    widget.plot_data(data)
    assert len(widget.current_data_list) == 1
    
    # 3. Changement de mode (Brut/Lissé)
    # On simule un clic physique pour que l'état du bouton change (Checked -> Unchecked)
    # Appeler juste toggle_mode() ne changeait pas l'état du bouton.
    widget.btn_mode.click()
    assert widget.display_mode == 'raw'
    
    # 4. Nettoyage
    widget.clear()
    assert len(widget.current_data_list) == 0

def test_mouse_interactions(qtbot):
    """Teste les interactions souris (Survol, Clic gauche, Clic droit)."""
    widget = PLRGraphWidget()
    qtbot.addWidget(widget)
    
    # Données pour avoir quelque chose à survoler
    df = pd.DataFrame({'timestamp_s': [0, 0.5, 1], 'diameter_mm': [5, 5, 5], 'diameter_smooth': [5, 5, 5]})
    widget.plot_data([{'df': df, 'label': 'T', 'color': 'r'}])
    
    # Mock d'un événement Matplotlib
    class MockEvent:
        def __init__(self, ax, x, y, btn=1):
            self.inaxes = ax
            self.xdata = x
            self.ydata = y
            self.button = btn
            self.guiEvent = None

    # 1. Test Survol (Hover)
    # On simule un mouvement de souris à t=0.5s
    evt_hover = MockEvent(widget.axes, 0.5, 5.0)
    widget.on_mouse_hover(evt_hover)
    assert widget.hover_annot.get_visible() is True
    
    # 2. Test Clic Gauche (Ajout Curseur)
    evt_click = MockEvent(widget.axes, 0.5, 5.0, btn=1)
    widget.on_mouse_click(evt_click)
    assert len(widget.cursors) == 1
    
    # 3. Test Clic Droit (Gommage)
    evt_rclick = MockEvent(widget.axes, 0.5, 5.0, btn=3)
    widget.on_mouse_click(evt_rclick) # Enclenche la gomme
    assert widget.is_erasing is True
    widget.on_mouse_hover(evt_hover)  # Efface en bougeant
    assert len(widget.cursors) == 0
    widget.on_mouse_release(evt_rclick) # Relâche
    assert widget.is_erasing is False

def test_results_dialog(qtbot):
    """Vérifie que la fenêtre de résultats s'ouvre."""
    df = pd.DataFrame({'timestamp_s': [0, 1], 'diameter_mm': [5, 5]})
    res = {'Metric': 1.0}
    dlg = PLRResultsDialog(data=df, results=res)
    qtbot.addWidget(dlg)
    assert dlg.table.rowCount() == 1