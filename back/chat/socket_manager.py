class SocketManager:
    def __init__(self):
        self.active_connection = None
    
    def set_connection(self, connection):
        self.active_connection = connection
    
    def get_connection(self):
        return self.active_connection
    
    def clear_connection(self):
        self.active_connection = None

socket_manager = SocketManager()