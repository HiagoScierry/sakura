class ServiceNotFound(Exception):
    def __init__(self, service_id: str) -> None:
        super().__init__(f'Serviço {service_id} não encontrado')
        self.service_id = service_id
