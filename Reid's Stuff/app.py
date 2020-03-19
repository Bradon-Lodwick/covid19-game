from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit, leave_room
import random

# Quick Note, client and user have been used interchangeably

class Client:
    def __init__(self, name, session_id):
        """
        :param name: The name of the client
        :param session_id: The clients current session, changes if they disconnect
        """

        # Username is chosen by the client when they join
        # Session id is used by the server to send messages to the correct client
        # Score is the clients current score
        self.username = name
        self.session = session_id
        self.score = 0


class ButtonRoulette:
    def __init__(self):
        # Active user is used as the key to the active client
        # Clients contains all clients that have connected this session even if they have left
        # Stock is the balance of points on the server
        # Punish Value is how many points players lose if they take the last stock
        self.active_user = ''
        self.clients = {}
        self.stock = random.randint(6, 9)
        self.punish_value = 10

    @property
    def first_client(self):
        # This is used to check if the joining client is the only one on the server

        # Clients session id is set to None if they have closed the window
        # active clients is a list containing only clients that are still connected
        active_clients = [client for client in self.clients.values() if client.session is not None]
        return len(active_clients) == 1

    @property
    def active_session(self):
        # Returns the session id of the current active user
        return self.clients[self.active_user].session

    @property
    def has_clients(self):
        return len(self.clients) != 0

    def join_client(self, name, session_id):
        """ Connects a client to the game

        :param name: The name of the joining user
        :param session_id: The current session of the user
        :return: True if the client is able to join, i.e. no active user has their name
        """
        # NOTE the return value is not currently used at this time

        # If no client is already using the username
        if name not in list(self.clients.keys()):
            self.clients[name] = Client(name, session_id)

            # Extra stock is added to help mitigate people immediately losing when they join
            self.stock += 4
            print(f"{name} has joined from: {session_id}")

            # If they are the first to join they are now the active player
            if self.first_client:
                self.active_user = name
            return True

        # If the client already exists but their session is None it means they had left and reconnected
        elif self.clients[name].session is None:
            # Only the session needs to be set
            self.clients[name].session = session_id
            print(f"{name} has returned from: {session_id}")
            return True

        # If it reaches this point there is already an active user with the username and they shouldn't join
        #TODO this return value is not currently used, duplicate players aren't informed
        else:
            return False

    def disconnect_client(self, session_id):
        """
        Disconnects the client from the game, but does not clear their score. They can rejoin later
        :param session_id: The session id of the player
        :return:
        """

        # Searches for the appropriate player and set's their session ID to None
        for key, value in self.clients.items():
            if value.session == session_id:
                self.clients[key].session = None
                print(f"{key} has disconnected")

    def score_of(self, name):
        """

        :param name: The name of the user
        :return: The score of the user
        """
        return self.clients[name].score

    def pass_turn(self, points_taken=0):
        """
        Takes the chosen amount of points from the stock and passes the turn to the next player
        :param points_taken: The amount of points to take from the stock
        :return: The message to send to the client
        """

        # Points are taken from the stock and are rewarded to the player if they don't take the last one
        self.stock -= points_taken
        if self.stock > 0:
            self.clients[self.active_user].score += points_taken
            msg = "YOU'RE SAFE"
        else:
            self.reset_score()
            self.clients[self.active_user].score -= self.punish_value
            msg = "YOU GOT GREEDY"

        # options is a list of all clients who are currently connected who are not the active player
        options = [key for key, value in list(self.clients.items()) if key != self.active_user and value.session is not None]
        if options:
            self.active_user = random.choice(options)
        print(f"Stock left: {self.stock}")
        return msg

    def reset_score(self):
        """
        Resets the score to a random value weighted by the number of active players
        :return:
        """
        active_clients = [client for client in self.clients.values() if client.session is not None]
        self.stock = (len(active_clients) + 1) * random.randint(2, 6)


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

@app.route('/')
def hello_world():
    return render_template('index.html')

# Initialize the game class
game = ButtonRoulette()

@socketio.on('joined')
def joined(data):
    """
    What to do when the client has joined the server
    :param data: The message sent by the client contains the username
    :return:
    """

    # user is the supplied name
    # Session_id is unique whenever the client reconnects
    user = data['username']
    session_id = request.sid
    
    # TODO Use the return to tell players that they couldn't join
    game.join_client(user, session_id)

    room = session_id
    join_room(room)

    if game.first_client:
        print(f"first client: {game.active_session}")

        # The client will respond to 'turn_update', state 0 will enable the buttons on the client side
        emit('turn_update', {'msg': 'YOUR TURN!', 'state' : 0}, room=game.active_session)
    else:
        print("not first client")

    # The client receives their score
    emit('score_update', {'score': game.score_of(user)}, room=session_id)

@socketio.on('disconnect')
def on_leave():
    """
    Called when a client closes or refreshes the window
    :return:
    """
    # If you leave the page without connecting to the game it still counts as disconnecting
    # If the game has no clients there will not be an active session
    if not game.has_clients:
        return

    session_id = request.sid

    room = session_id
    leave_room(room)

    # If the player who left is the active player a new player will be chosen
    if session_id == game.active_session:
        game.pass_turn()
        emit('turn_update', {'msg': 'YOUR TURN!', 'state': '0'}, room=game.active_session)

    game.disconnect_client(session_id)

@socketio.on('trigger')
def handle_trigger(data):
    """
    When the player takes points from the stock it calls the trigger method
    :param data: contains the user that sent the message ans how many points they took
    :return:
    """
    user = data['username']
    session_id = request.sid
    points_taken = data['points']

    # Changes the active player
    result = game.pass_turn(points_taken)

    # State 1 disables the clients buttons, result will tell them what happened to their points
    # Note that these two messages send to session_id, this is responding to the client who sent the trigger
    emit('turn_update', {'msg': result, 'state': '1'}, room=session_id)
    emit('score_update', {'score': game.score_of(user)}, room=session_id)

    # Informs the active player that it is now their turn
    # Note: this will be the same player if they are alone
    emit('turn_update', {'msg': 'YOUR TURN!', 'state' : '0'}, room=game.active_session)


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port='25565')
