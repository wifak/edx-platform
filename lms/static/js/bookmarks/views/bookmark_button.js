;(function (define, undefined) {
    'use strict';
    define(['gettext', 'jquery', 'underscore', 'backbone', 'js/views/message'],
        function (gettext, $, _, Backbone, MessageView) {

        return Backbone.View.extend({

            errorIcon: '<i class="fa fa-fw fa-exclamation-triangle message-error" aria-hidden="true"></i>',
            errorMessage: gettext('An error has occurred. Please try again.'),

            srAddBookmarkText: gettext('Click to bookmark this unit'),
            srRemoveBookmarkText: gettext('Click to remove bookmark from this unit'),

            events: {
                'click .bookmark-button': 'bookmark'
            },

            initialize: function (options) {
                this.bookmarked = options.bookmarked;

                this.errorMessageView = new MessageView({
                    el: $('.coursewide-message-banner'),
                    templateId: '#message_banner-tpl'
                });
                this.bookmarksUrl = $(".courseware-bookmarks-button").data('bookmarksApiUrl');
                this.updateBookmarkState(this.bookmarked);
            },

            bookmark: function(event) {
                event.preventDefault();

                var $buttonElement = $(event.currentTarget);
                var bookmarkId = $buttonElement.data("bookmarkId");

                if ($buttonElement.hasClass('bookmarked')) {
                    this.removeBookmark($buttonElement, bookmarkId);
                } else {
                    this.addBookmark($buttonElement, bookmarkId);
                }
            },

            addBookmark: function($buttonElement, bookmarkId) {
                var view = this;
                var usageId = bookmarkId.split(',')[1];
                $.ajax({
                    data: {usage_id: usageId},
                    type: "POST",
                    url: view.bookmarksUrl,
                    dataType: 'json',
                    success: function () {
                        $buttonElement.trigger('bookmark:add');
                        $buttonElement.removeClass('un-bookmarked').addClass('bookmarked');
                        $buttonElement.attr('aria-pressed', 'true');
                        $buttonElement.find('.bookmark-sr').text(view.srRemoveBookmarkText);
                    },
                    error: function() {
                        view.errorMessageView.showMessage(view.errorMessage, view.errorIcon);
                    }
                });
            },

            removeBookmark: function($buttonElement, bookmarkId) {
                var view = this;
                var deleteUrl = view.bookmarksUrl + bookmarkId + '/';
                $.ajax({
                    type: "DELETE",
                    url: deleteUrl,
                    success: function () {
                        $buttonElement.trigger('bookmark:remove');
                        $buttonElement.removeClass('bookmarked').addClass('un-bookmarked');
                        $buttonElement.attr('aria-pressed', 'false');
                        $buttonElement.find('.bookmark-sr').text(view.srAddBookmarkText);
                    },
                    error: function() {
                        view.errorMessageView.showMessage(view.errorMessage, view.errorIcon);
                    }
                });
            },

            updateBookmarkState: function(isBookmarked) {
                var $bookmarkButton = this.$el.find('.bookmark-button');
                if (isBookmarked) {
                    //this.$el.trigger('bookmark:add');
                    $bookmarkButton.addClass("bookmarked").removeClass("un-bookmarked");
                    $bookmarkButton.find('.bookmark-sr').text(this.srRemoveBookmarkText);
                } else {
                    //this.$el.trigger('bookmark:remove');
                    $bookmarkButton.find('.bookmark-sr').text(this.srAddBookmarkText);
                    $bookmarkButton.addClass("un-bookmarked").removeClass("bookmarked");
                }
            }
        });
    });
}).call(this, define || RequireJS.define);
