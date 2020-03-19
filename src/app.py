#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import random

from flask import Flask, request, redirect, render_template
from flask_bootstrap import Bootstrap
from flask_socketio import SocketIO, emit

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# Setup the app
app = Flask(__name__)
Bootstrap(app)
socket_io_app = SocketIO(app)


# TODO replace clients dict with db interactions
usernames_by_sid = {}
game_active = False


@app.route("/", methods=["GET", "POST"])
def connect_to_game():
    """
    Joins the game.
    """

    if request.method == "POST":
        # Get the username they provided
        return redirect("game_page")
    else:
        return render_template("connect_to_game.html")


@app.route("/game", methods=["GET"])
def game_page():
    # Get the username for the user
    username = request.args["username"]
    return render_template("game.html", username=username)


@socket_io_app.on('joined')
def joined(data):
    global game_active
    logger.info(f"user connected:{request.sid}:{data['username']}")

    # TODO add the user's session to the database
    username = data["username"]
    usernames_by_sid[request.sid] = username

    if not game_active:
        game_active = True
        # Start the game
        next_players_turn()


@socket_io_app.on('disconnect')
def on_disconnect():
    # Remove active username data
    username = usernames_by_sid.pop(request.sid)
    logger.info(f"user disconnected:{request.sid}:{username}")


@socket_io_app.on('turn_taken')
def take_turn(data):
    points_taken = data["pointsTaken"]
    logger.info(f"turn taken:{request.sid}:{usernames_by_sid[request.sid]}points={points_taken}")
    next_players_turn()


def next_players_turn():
    """
    Sends a message to the next turn player, and updates the global values that represent which player's turn the system
    is waiting on.
    """

    # TODO select next turn player from connected players in the db
    next_player = random.choice(list(usernames_by_sid.values()))
    emit("turn_update", {"username": next_player})


socket_io_app.run(app, host="0.0.0.0", port=5001)
