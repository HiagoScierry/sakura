from chalice import Chalice

from chalicelib.entrypoints import jobs
from chalicelib.entrypoints.api import auth, monitoring, services

app = Chalice(app_name='chalice-api')

app.register_blueprint(auth.bp)
app.register_blueprint(monitoring.bp)
app.register_blueprint(services.bp)
app.register_blueprint(jobs.bp)
