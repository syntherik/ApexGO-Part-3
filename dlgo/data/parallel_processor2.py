from __future__ import print_function
from __future__ import absolute_import
import os
import glob
import os.path
import tarfile
import gzip
import shutil
import numpy as np
import multiprocessing
from os import sys
from keras.utils import to_categorical

from dlgo.gosgf import SgfGame
from dlgo.goboard_fast import Board, GameState, Move
from dlgo.gotypes import Player, Point
from dlgo.data.index_processor import KGSIndex
from dlgo.data.sampling import Sampler
from dlgo.data.generator import DataGenerator
from dlgo.encoders.base import get_encoder_by_name

import math


def worker(jobinfo):
    try:
        clazz, encoder, zip_file, data_file_name, game_list = jobinfo
        clazz(encoder=encoder).process_zip(zip_file, data_file_name, game_list)
    except (KeyboardInterrupt, SystemExit):
        raise Exception('>>> Exiting child process.')


class GoDataProcessor:
    def __init__(self, encoder='oneplane', data_directory='data'):
        self.encoder_string = encoder
        self.encoder = get_encoder_by_name(encoder, 19)
        self.data_dir = data_directory

    def load_go_data(self, data_type='train', num_samples=1000,
                     use_generator=False):
        index = KGSIndex(data_directory=self.data_dir)
        index.download_files()

        sampler = Sampler(data_dir=self.data_dir)
        data = sampler.draw_data(data_type, num_samples)

        self.map_to_workers(data_type, data)
        if use_generator:
            generator = DataGenerator(self.data_dir, data)
            return generator
        else:
            features_and_labels = self.consolidate_games(data_type, data)
            return features_and_labels

    def unzip_data(self, zip_file_name):
        this_gz = gzip.open(self.data_dir + '/' + zip_file_name)

        tar_file = zip_file_name[0:-3]
        this_tar = open(self.data_dir + '/' + tar_file, 'wb')

        shutil.copyfileobj(this_gz, this_tar)
        this_tar.close()
        return tar_file

    """
    def process_zip(self, zip_file_name, data_file_name, game_list):
        feature_file_base = self.data_dir + '/' + data_file_name + '_features_%d'
        label_file_base = self.data_dir + '/' + data_file_name + '_labels_%d'

        print(f"processing {data_file_name}...")

        tar_file = self.unzip_data(zip_file_name)
        zip_file = tarfile.open(self.data_dir + '/' + tar_file)
        name_list = zip_file.getnames()
        total_examples = self.num_total_examples(zip_file, game_list, name_list)

        shape = self.encoder.shape()
        feature_shape = np.insert(shape, 0, np.asarray([total_examples]))
        features = np.zeros(feature_shape)
        labels = np.zeros((total_examples,))

        counter = 0
        for index in game_list:
            name = name_list[index + 1]
            if not name.endswith('.sgf'):
                raise ValueError(name + ' is not a valid sgf')
            sgf_content = zip_file.extractfile(name).read()
            sgf = SgfGame.from_string(sgf_content)

            game_state, first_move_done = self.get_handicap(sgf)

            for item in sgf.main_sequence_iter():
                color, move_tuple = item.get_move()
                point = None
                if color is not None:
                    if move_tuple is not None:
                        row, col = move_tuple
                        point = Point(row + 1, col + 1)
                        move = Move.play(point)
                    else:
                        move = Move.pass_turn()
                    if first_move_done and point is not None:
                        features[counter] = self.encoder.encode(game_state)
                        labels[counter] = self.encoder.encode_point(point)
                        counter += 1
                    game_state = game_state.apply_move(move)
                    first_move_done = True

        chunk = 0
        chunksize = 1024

        # Does not do what author thinks it does -- truncates data
        # while features.shape[0] >= chunksize:
        #     feature_file = feature_file_base % chunk
        #     label_file = label_file_base % chunk
        #     chunk += 1
        #     current_features, features = features[:chunksize], features[chunksize:]
        #     current_labels, labels = labels[:chunksize], labels[chunksize:]
        #     np.save(feature_file, current_features)
        #     np.save(label_file, current_labels)

        # fixed code:
        while features.shape[0] > 0:
            feature_file = feature_file_base % chunk
            label_file = label_file_base % chunk
            chunk += 1

            current_features, features = features[:chunksize], features[chunksize:]
            current_labels, labels = labels[:chunksize], labels[chunksize:]

            np.save(feature_file, current_features)
            print(f'wrote {feature_file}')

            np.save(label_file, current_labels)
            print(f'wrote {label_file}')

        # allow garbage collection
        features = None
        labels = None
        current_features = None
        current_labels = None
    """

    def process_zip(self, zip_file_name, data_file_name, game_list):
        # total number of moves in all games in zip file
        tar_file = self.unzip_data(zip_file_name)
        zip_file = tarfile.open(self.data_dir + '/' + tar_file)
        name_list = zip_file.getnames()
        total_examples = self.num_total_examples(zip_file, game_list, name_list)
        new_game_list = game_list.copy()
        # shape = self.encoder.shape()
        # Changed code to prevent too big features in memory
        # Finish implementation of process_zip
        feature_file_base = self.data_dir + '/' + data_file_name + '_features_%d'
        label_file_base = self.data_dir + '/' + data_file_name + '_labels_%d'
        chunk = 0
        examples_used = 1024
        iters = math.ceil(total_examples / examples_used)
        for z in range(iters):
            # feature_shape = np.insert(shape, 0, np.asarray([examples_used]))
            # features = np.zeros(feature_shape)
            # labels = np.zeros((examples_used,))
            # counter = 0
            for index in new_game_list[:examples_used]:
                features = []
                labels = []
                # reads the SGF contents as a string
                name = name_list[index + 1]
                if not name.endswith('.sgf'):
                    raise ValueError(name + ' is not a valid sgf')
                sgf_content = zip_file.extractfile(name).read()
                sgf = SgfGame.from_string(sgf_content)
                # apply handicap stones
                game_state, first_move_done = self.get_handicap(sgf)
                # iterates through all moves

                for item in sgf.main_sequence_iter():
                    color, move_tuple = item.get_move()
                    point = None
                    if color is not None:
                        # read the coordinate of the stone to be played
                        if move_tuple is not None:
                            row, col = move_tuple
                            point = Point(row + 1, col + 1)
                            move = Move.play(point)
                        else:
                            # or do nothing
                            move = Move.pass_turn()
                        if first_move_done and point is not None:
                            # Encode the current games state as features
                            # features[counter] = self.encoder.encode(game_state)
                            z = self.encoder.encode(game_state)
                            features.append(z)
                            # Encode the next move as label
                            # labels[counter] = self.encoder.encode_point(point)
                            labels.append(self.encoder.encode_point(point))
                            # counter += 1
                        # Apply the move and move on to the next one.
                        game_state = game_state.apply_move(move)
                        first_move_done = True
                new_game_list = new_game_list[examples_used:]
                feature_file = feature_file_base % chunk
                label_file = label_file_base % chunk
                chunk += 1

                # current_features, features = features[:examples_used], features[examples_used:]
                # current_labels, labels = labels[:examples_used], labels[examples_used:]

                # np.save(feature_file, current_features)
                # np.save(label_file, current_labels)
                features = np.array(features)
                labels = np.array(labels)
                np.save(feature_file, features)
                np.save(label_file, labels)
        #

    def consolidate_games(self, name, samples):
        files_needed = set(file_name for file_name, index in samples)
        file_names = []
        for zip_file_name in files_needed:
            file_name = zip_file_name.replace('.tar.gz', '') + name
            file_names.append(file_name)

        feature_list = []
        label_list = []
        for file_name in file_names:
            file_prefix = file_name.replace('.tar.gz', '')
            base = self.data_dir + '/' + file_prefix + '_features_*.npy'
            for feature_file in glob.glob(base):
                label_file = feature_file.replace('features', 'labels')
                x = np.load(feature_file)
                y = np.load(label_file)
                x = x.astype('float32')
                y = to_categorical(y.astype(int), 19 * 19)
                feature_list.append(x)
                label_list.append(y)

        features = np.concatenate(feature_list, axis=0)
        labels = np.concatenate(label_list, axis=0)

        feature_file = self.data_dir + '/' + name
        label_file = self.data_dir + '/' + name

        np.save(feature_file, features)
        np.save(label_file, labels)

        return features, labels

    @staticmethod
    def get_handicap(sgf):
        go_board = Board(19, 19)
        first_move_done = False
        move = None
        game_state = GameState.new_game(19)
        if sgf.get_handicap() is not None and sgf.get_handicap() != 0:
            for setup in sgf.get_root().get_setup_stones():
                for move in setup:
                    row, col = move
                    go_board.place_stone(Player.black, Point(row + 1, col + 1))
            first_move_done = True
            game_state = GameState(go_board, Player.white, None, move)
        return game_state, first_move_done

    def map_to_workers(self, data_type, samples):
        zip_names = set()
        indices_by_zip_name = {}
        for filename, index in samples:
            zip_names.add(filename)
            if filename not in indices_by_zip_name:
                indices_by_zip_name[filename] = []
            indices_by_zip_name[filename].append(index)

        zips_to_process = []
        for zip_name in zip_names:
            base_name = zip_name.replace('.tar.gz', '')
            data_file_name = base_name + data_type
            if not os.path.isfile(self.data_dir + '/' + data_file_name):
                zips_to_process.append((self.__class__, self.encoder_string, zip_name,
                                        data_file_name, indices_by_zip_name[zip_name]))

        cores = multiprocessing.cpu_count()
        pool = multiprocessing.Pool(processes=cores)
        p = pool.map_async(worker, zips_to_process)
        try:
            _ = p.get()
        except KeyboardInterrupt:
            pool.terminate()
            pool.join()
            sys.exit(-1)

    def num_total_examples(self, zip_file, game_list, name_list):
        total_examples = 0
        for index in game_list:
            name = name_list[index + 1]
            if name.endswith('.sgf'):
                sgf_content = zip_file.extractfile(name).read()
                sgf = SgfGame.from_string(sgf_content)
                game_state, first_move_done = self.get_handicap(sgf)

                num_moves = 0
                for item in sgf.main_sequence_iter():
                    color, move = item.get_move()
                    if color is not None:
                        if first_move_done:
                            num_moves += 1
                        first_move_done = True
                total_examples = total_examples + num_moves
            else:
                raise ValueError(name + ' is not a valid sgf')
        return total_examples


if __name__ == '__main__':
    multiprocessing.freeze_support()