#  (C) Copyright Wieger Wesselink 2021. Distributed under the GPL-3.0-or-later
#  Software License, (See accompanying file LICENSE or copy at
#  https://www.gnu.org/licenses/gpl-3.0.txt)

import random
import time
import copy
import numpy as np
from competitive_sudoku.sudoku import GameState, Move, SudokuBoard, TabooMove
import competitive_sudoku.sudokuai


class SudokuAI(competitive_sudoku.sudokuai.SudokuAI):
    """
    Sudoku AI that computes a move for a given sudoku configuration.
    """

    def __init__(self):
        super().__init__()

    # N.B. This is a very naive implementation.
    def compute_best_move(self, game_state: GameState) -> None:
        #==========================================================================
        # Generate all legal moves from a given game state / board position

        #defining some variables for an organized view of the code
        self.N = game_state.board.N #board is N*N squares || N=n*m
        self.n = game_state.board.n #block is n squares wide || board is n blocks high
        self.m = game_state.board.m #block is m squares high || board is m squares wide
        self.squares = game_state.board.squares #list of all values (row-wise)

        #grouping the squares in the same region together (a region is either a row, a column or a block)
        self.dct_regions = {}

        for index in range(self.N):
            self.dct_regions[f"row{index}"] = [(index, j) for j in range(self.N)] #squares in the same row
            self.dct_regions[f"column{index}"] = [(i, index) for i in range(self.N)] #squares in the same column
        
        counter=1
        for width in range(self.n):
            for height in range(self.m):
                self.dct_regions[f"block{counter}"] = [(i, j) for i in range(width*self.m, width*self.m+self.m) for j in range(height*self.n, height*self.n+self.n)] #squares in the same block
                counter+=1
        
        #function that checks if the move would be possible according to some constraints
        def possible(i, j, value):
            """ Checks whether
                - the cell the move is going to be made in is empty, 
                - the move is not a taboo move, and 
                - the value that would be written in the cell is not already in another 
                  cell in the same row, column or block (check for uniqueness) 
            """

            #all groups of cells that cell (i, j) is part of
            regions_with_ij = [group for group in list(self.dct_regions.values()) if (i, j) in group]

            #all values that are already in the same row, column or block which cell (i, j) is part of;
            #making a move by filling in these values in cell (i, j) would make the move illegal
            values_already_in_rcb_ij = set([game_state.board.get(i, j) for group in regions_with_ij for (i,j) in group])
            
            return game_state.board.get(i, j) == SudokuBoard.empty \
                   and not TabooMove(i, j, value) in game_state.taboo_moves \
                   and value not in values_already_in_rcb_ij

        #all legal moves
        self.all_moves = [Move(i, j, value) for i in range(self.N) for j in range(self.N)
                     for value in range(1, self.N+1) if possible(i, j, value)]
        self.all_moves_tuples = [((move.i, move.j), move.value) for move in self.all_moves]

        #propose an initial move before the timer runs out
        if self.squares.count(SudokuBoard.empty) < self.N*self.N: #if at least one square already filled in; not an empty board
            least_occurring_coordinate = sorted([(tup[0], self.all_moves_tuples.count(tup[0])) for tup in self.all_moves_tuples], key=lambda l: l[-1])[0][0]
            for (ij, val) in self.all_moves_tuples:
                if ij[0]==least_occurring_coordinate[0]:
                    if ij[1]==least_occurring_coordinate[1]:
                        self.propose_move(Move(ij[0], ij[1], val))
        else: #if board empty, play a random move
            self.propose_move(random.choice(self.all_moves))
        

        #==========================================================================
        # Evaluation function that assigns a numerical score to any game state

        def evaluate(game_state: GameState):
            """ Return numerical evaluation of state 
                (=difference in points between players)
            """
            #the evaluation function depends on the current player; the current player is the maximising player and their opponent is the minimising player
            if game_state.current_player == 1:
                return game_state.scores[0]-game_state.scores[1]
            else:
                return game_state.scores[1]-game_state.scores[0]

        #==========================================================================
        # Function to obtain all the children states of the current state

        def getChildren(game_state: GameState):
            """ Returns list of states that follow from state """
            moves = []

            #dictionary with amount of empty squares per region
            dct_empty_squares = {}
            for region in self.dct_regions:
                values = [game_state.board.get(i, j) for (i, j) in self.dct_regions[region]]
                empty_squares = values.count(SudokuBoard.empty)
                dct_empty_squares[region] = empty_squares
                
                # if there are only 1 square in 1 or more regions, only compare these moves
                empty_values = np.where(np.array(values) == 0)[0]
                if len(empty_values) == 1:
                    ij = self.dct_regions[region][values.index(0)]
                    for (coordinates, val) in self.all_moves_tuples:
                        if ij[0] == coordinates[0] and ij[1] == coordinates[1]:
                                moves.append(Move(ij[0], ij[1], val))
                
            #dictionary with scores based on how many regions the move completes
            dct_scores = {0: 0, #completing 0 regions will give 0 points
                        1: 1, #completing 1 region will give 1 points
                        2: 3, #completing 2 regions will give 3 points
                        3: 7} #completing 3 regions will give 7 points

            #giving each move a score based on how many region it completes
            lst_scores = []
            for move in self.all_moves:
                regions_concerned = [region for region, coordinates in self.dct_regions.items() if (move.i, move.j) in coordinates]
                empty_in_regions = [dct_empty_squares[region] for region in regions_concerned]
                lst_scores.append(dct_scores[empty_in_regions.count(1)])
            
            #combine move and evaluation score
            dct_move_score = dict(zip(self.all_moves_tuples, lst_scores))

            #get the children states
            if len(moves) > 0:
                children=[]
                for move in moves:
                    child_state = copy.deepcopy(game_state)
                    child_state.board.put(move.i, move.j, move.value)
                    child_state.taboo_moves.append(move)
                    child_state.moves.append(move)
                    if game_state.current_player() == 1:
                        child_state.scores[0] += dct_move_score[((move.i, move.j), move.value)]
                    else: 
                        child_state.scores[1] += dct_move_score[((move.i, move.j), move.value)]
                    children.append(child_state)
                return children
            else: 
                children=[]
                for move in self.all_moves:
                    child_state = copy.deepcopy(game_state)
                    child_state.board.put(move.i, move.j, move.value)
                    child_state.taboo_moves.append(move)
                    child_state.moves.append(move)
                    if game_state.current_player() == 1:
                        child_state.scores[0] += dct_move_score[((move.i, move.j), move.value)]
                    else: 
                        child_state.scores[1] += dct_move_score[((move.i, move.j), move.value)]
                    children.append(child_state)
                return children
        
        #==========================================================================
        # Minimax tree search algorithm

        def minimax(game_state: GameState, depth, isMaximisingPlayer):
            """ Recursively evaluate nodes in tree """

            if depth==0:
                return evaluate(game_state)
        
            children=getChildren(game_state)
            if isMaximisingPlayer:
                value = float("-inf")
                for child in children:
                    if minimax(child, depth-1, not isMaximisingPlayer) > value:
                        best_state = child
                    value = max(value, minimax(child, depth-1, not isMaximisingPlayer))
                for move in best_state.moves:
                    if move not in game_state.moves:
                        self.propose_move(move)
                return value
            else:
                value = float("inf")
                for child in children:
                    value = min(value, minimax(child, depth-1, not isMaximisingPlayer))
                return value

        depth = self.squares.count(SudokuBoard.empty) #amount of empty squares
        isMaximisingPlayer = True

        minimax(game_state, depth, isMaximisingPlayer)
        

#python simulate_game.py --first team05_A1_v2 --board "boards/empty-3x3.txt"
#python simulate_game.py --first team05_A1_v2 --second greedy_player --board "boards/empty-3x3.txt"
