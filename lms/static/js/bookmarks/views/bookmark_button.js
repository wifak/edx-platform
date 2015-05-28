;(function (define, undefined) {
    'use strict';
    define(['gettext', 'jquery', 'underscore', 'backbone', 'js/views/message'],
        function (gettext, $, _, Backbone, MessageView) {

        return Backbone.View.extend({

            el: '.course-content',

            errorIcon: '<i class="fa fa-fw fa-exclamation-triangle message-error" aria-hidden="true"></i>',
            errorMessage: gettext('An error has occurred. Please try again.'),

            srAddBookmarkText: gettext('Click to bookmark this unit'),
            srRemoveBookmarkText: gettext('Click to remove bookmark from this unit'),

            events: {
                'click .bookmark-button': 'bookmark',
                'sequence:changed .sequence': 'updateBookmarkState'
            },

            initialize: function () {
                this.errorMessageView = new MessageView({
                    el: $('.coursewide-message-banner'),
                    templateId: '#message_banner-tpl'
                });
            },

            bookmark: function(event) {
                event.preventDefault();

                var $buttonElement = $(event.currentTarget);
                var usageId = $buttonElement.data("id");
                $buttonElement.attr("disabled", true).addClass('is-disabled');

                if ($buttonElement.hasClass('bookmarked')) {
                    this.removeBookmark($buttonElement, usageId);
                } else {
                    this.addBookmark($buttonElement, usageId);
                }
            },

            addBookmark: function($buttonElement, usageId) {
                var postUrl = $buttonElement.data('url');
                var view = this;
                $.ajax({
                    data: {usage_id: usageId},
                    type: "POST",
                    url: postUrl,
                    dataType: 'json',
                    success: function () {
                        $('.seq-book.active').find('.bookmark-icon').removeClass('is-hidden').addClass('bookmarked');
                        $buttonElement.removeClass('un-bookmarked').addClass('bookmarked');
                        $buttonElement.attr('aria-pressed', 'true');
                        $buttonElement.find('.bookmark-sr').text(view.srRemoveBookmarkText);
                    },
                    error: function() {
                        view.errorMessageView.showMessage(view.errorMessage, view.errorIcon);
                    },
                    complete: function () {
                        $buttonElement.attr("disabled", false).removeClass('is-disabled');
                    }
                });
            },

            removeBookmark: function($buttonElement, usageId) {
                var deleteUrl = $buttonElement.data('url') + $buttonElement.data('username') + ',' + usageId;
                var view = this;
                $.ajax({
                    type: "DELETE",
                    url: deleteUrl,
                    success: function () {
                        $('.seq-book.active').find('.bookmark-icon').removeClass('bookmarked').addClass('is-hidden');
                        $buttonElement.removeClass('bookmarked').addClass('un-bookmarked');
                        $buttonElement.attr('aria-pressed', 'false');
                        $buttonElement.find('.bookmark-sr').text(view.srAddBookmarkText);
                    },
                    error: function() {
                        view.errorMessageView.showMessage(view.errorMessage, view.errorIcon);
                    },
                    complete: function () {
                        $buttonElement.attr("disabled", false).removeClass('is-disabled');
                    }
                });
            },

            updateBookmarkState: function(event) {
                var $currentElement = $(event.currentTarget);
                var $bookmarkButton = $currentElement.find('.bookmark-button');
                if ($currentElement.find('.active').find('.bookmark-icon').hasClass('bookmarked')) {
                    $bookmarkButton.addClass("bookmarked").removeClass("un-bookmarked");
                    $bookmarkButton.find('.bookmark-sr').text(this.srRemoveBookmarkText);
                } else {
                    $bookmarkButton.find('.bookmark-sr').text(this.srAddBookmarkText);
                    $bookmarkButton.addClass("un-bookmarked").removeClass("bookmarked");
                }
            }
        });
    });
}).call(this, define || RequireJS.define);
