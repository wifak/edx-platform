RequireJS.require([
    'js/bookmarks/views/bookmarks_list_button',
    'js/bookmarks/views/bookmark_button'
], function (BookmarksListButton, BookmarkButton) {
    'use strict';

    new BookmarkButton();
    return new BookmarksListButton();
});
