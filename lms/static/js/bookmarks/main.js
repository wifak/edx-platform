RequireJS.require([
    'js/bookmarks/views/bookmarks_button',
    'js/bookmarks/views/bookmark-button'
], function (BookmarksButton, BookmarkButton) {
    'use strict';

    new BookmarkButton();
    return new BookmarksButton();
});
