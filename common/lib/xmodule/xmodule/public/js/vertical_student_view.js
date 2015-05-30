/* JavaScript for Vertical Student View. */
window.VerticalStudentView = function (runtime, element) {

    RequireJS.require(['js/bookmarks/views/bookmark_button'], function (BookmarkButton) {
            var $element = $(element);

            return new BookmarkButton({el: $element, bookmarked: $element.parent('#seq_content').data('bookmarked')});
        });

};
