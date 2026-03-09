from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton
import pyqtgraph.opengl as gl
import numpy as np

class Table3DDialog(QDialog):
    def __init__(self, name, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"3D Visualizer: {name}")
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # GL Viewport
        self.view = gl.GLViewWidget()
        self.view.setCameraPosition(distance=50)
        layout.addWidget(self.view)
        
        # Grid
        g = gl.GLGridItem()
        g.scale(2, 2, 1)
        self.view.addItem(g)
        
        self.plot_surface(data)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def plot_surface(self, data):
        try:
            z = np.array(data)
            rows, cols = z.shape
            x = np.linspace(-10, 10, cols)
            y = np.linspace(-10, 10, rows)
            
            p = gl.GLSurfacePlotItem(x=x, y=y, z=z, shader='shaded', color=(0.5, 0.5, 1, 1))
            self.view.addItem(p)
        except Exception as e:
            print(f"3D Plot error: {e}")
