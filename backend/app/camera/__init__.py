"""Camera drivers and streaming.

Nothing outside this package may import ``picamera2``. Application code depends only on the
:class:`~app.camera.base.Camera` protocol; the concrete driver is chosen at runtime by
:func:`~app.camera.manager.select_camera`.
"""
