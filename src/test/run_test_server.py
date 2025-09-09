# Simply starts the test server. Can be used for manual testing
from simulator import ssh_server

if __name__ == "__main__":
    sim = ssh_server.InstrumentServerSimulator()
    sim.start()
    input("Press Enter to stop the server...\n")
    sim.stop()