# This file is part of beets.
# Copyright 2016, Stig Inge Lea Bjornsen.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.


"""Tests for the `importadded` plugin."""

import os

import pytest

from beets import importer
from beets.test.helper import AutotagImportTestCase, PluginMixin
from beets.util import displayable_path, syspath
from beetsplug.importadded import ImportAddedPlugin

_listeners = ImportAddedPlugin.listeners


def preserve_plugin_listeners():
    """Preserve the initial plugin listeners as they would otherwise be
    deleted after the first setup / tear down cycle.
    """
    if not ImportAddedPlugin.listeners:
        ImportAddedPlugin.listeners = _listeners


def modify_mtimes(paths, offset=-60000):
    for i, path in enumerate(paths, start=1):
        mstat = os.stat(path)
        os.utime(syspath(path), (mstat.st_atime, mstat.st_mtime + offset * i))


class ImportAddedTest(PluginMixin, AutotagImportTestCase):
    # The minimum mtime of the files to be imported
    plugin = "importadded"
    min_mtime = None

    def setUp(self):
        preserve_plugin_listeners()
        super().setUp()
        self.prepare_album_for_import(2)
        # Different mtimes on the files to be imported in order to test the
        # plugin
        modify_mtimes(mfile.path for mfile in self.import_media)
        self.min_mtime = min(
            os.path.getmtime(mfile.path) for mfile in self.import_media
        )
        self.importer = self.setup_importer()
        self.importer.add_choice(importer.Action.APPLY)

    def find_media_file(self, item):
        """Find the pre-import MediaFile for an Item"""
        for m in self.import_media:
            if m.title.replace("Tag", "Applied") == item.title:
                return m
        raise AssertionError(
            "No MediaFile found for Item " + displayable_path(item.path)
        )

    def test_import_album_with_added_dates(self):
        self.importer.run()

        album = self.lib.albums().get()
        assert album.added == self.min_mtime
        for item in album.items():
            assert item.added == self.min_mtime

    def test_import_album_inplace_with_added_dates(self):
        self.config["import"]["copy"] = False

        self.importer.run()

        album = self.lib.albums().get()
        assert album.added == self.min_mtime
        for item in album.items():
            assert item.added == self.min_mtime

    def test_import_album_with_preserved_mtimes(self):
        self.config["importadded"]["preserve_mtimes"] = True
        self.importer.run()
        album = self.lib.albums().get()
        assert album.added == self.min_mtime
        for item in album.items():
            assert item.added == pytest.approx(self.min_mtime, rel=1e-4)
            mediafile_mtime = os.path.getmtime(self.find_media_file(item).path)
            assert item.mtime == pytest.approx(mediafile_mtime, rel=1e-4)
            assert os.path.getmtime(item.path) == pytest.approx(
                mediafile_mtime, rel=1e-4
            )

    def test_reimported_album_skipped(self):
        # Import and record the original added dates
        self.importer.run()
        album = self.lib.albums().get()
        album_added_before = album.added
        items_added_before = {item.path: item.added for item in album.items()}
        # Newer Item path mtimes as if Beets had modified them
        modify_mtimes(items_added_before.keys(), offset=10000)
        # Reimport
        self.setup_importer(import_dir=self.libdir)
        self.importer.run()
        # Verify the reimported items
        album = self.lib.albums().get()
        assert album.added == pytest.approx(album_added_before, rel=1e-4)
        items_added_after = {item.path: item.added for item in album.items()}
        for item_path, added_after in items_added_after.items():
            assert items_added_before[item_path] == pytest.approx(
                added_after, rel=1e-4
            ), "reimport modified Item.added for " + displayable_path(item_path)

    def test_import_singletons_with_added_dates(self):
        self.config["import"]["singletons"] = True
        self.importer.run()
        for item in self.lib.items():
            mfile = self.find_media_file(item)
            assert item.added == pytest.approx(
                os.path.getmtime(mfile.path), rel=1e-4
            )

    def test_import_singletons_with_preserved_mtimes(self):
        self.config["import"]["singletons"] = True
        self.config["importadded"]["preserve_mtimes"] = True
        self.importer.run()
        for item in self.lib.items():
            mediafile_mtime = os.path.getmtime(self.find_media_file(item).path)
            assert item.added == pytest.approx(mediafile_mtime, rel=1e-4)
            assert item.mtime == pytest.approx(mediafile_mtime, rel=1e-4)
            assert os.path.getmtime(item.path) == pytest.approx(
                mediafile_mtime, rel=1e-4
            )

    def test_reimported_singletons_skipped(self):
        self.config["import"]["singletons"] = True
        # Import and record the original added dates
        self.importer.run()
        items_added_before = {
            item.path: item.added for item in self.lib.items()
        }
        # Newer Item path mtimes as if Beets had modified them
        modify_mtimes(items_added_before.keys(), offset=10000)
        # Reimport
        self.setup_importer(import_dir=self.libdir, singletons=True)
        self.importer.run()
        # Verify the reimported items
        items_added_after = {item.path: item.added for item in self.lib.items()}
        for item_path, added_after in items_added_after.items():
            assert items_added_before[item_path] == pytest.approx(
                added_after, rel=1e-4
            ), "reimport modified Item.added for " + displayable_path(item_path)
