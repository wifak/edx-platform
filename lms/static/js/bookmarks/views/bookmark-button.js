;(function (define, undefined) {
    'use strict';
    define(['gettext', 'jquery', 'underscore', 'backbone', 'js/views/message'],
        function (gettext, $, _, Backbone, MessageView) {

        return Backbone.View.extend({

            el: '#seq_content',

            inProgressElement: '#loading-message',
            errorMessageElement: '#error-message',

            errorIcon: '<i class="fa fa-fw fa-exclamation-triangle message-error" aria-hidden="true"></i>',
            inProgressIcon: '<i class="fa fa-fw fa-spinner fa-pulse message-in-progress" aria-hidden="true"></i>',

            errorMessage: gettext('An error has occurred. Please try again.'),

            events: {
                'click .bookmark-button': 'bookmark'
            },

            initialize: function () {
                this.inProgressView = new MessageView({el: $(this.inProgressElement)});
                this.errorMessageView = new MessageView({el: $(this.errorMessageElement)});
            },

            bookmark: function(event) {
                event.preventDefault();
                var $buttonElement = $(event.currentTarget);
                var usageId = $buttonElement.data("id");

                this.inProgressView.showMessage('', this.inProgressIcon);
                $buttonElement.attr("disabled", true).addClass('is-disabled');

                if ($buttonElement.hasClass('bookmarked')) {
                    this.removeBookmark($buttonElement, usageId);
                } else {
                    this.addBookmark($buttonElement, usageId);
                }
            },

            addBookmark: function($this, usageId) {
                var postUrl = $this.data('url');
                var that = this;
                $.ajax({
                    data: {usage_id: usageId},
                    type: "POST",
                    url: postUrl,
                    dataType: 'json',
                    success: function () {
                        $('.seq-book.active').find('.bookmark-icon').removeClass('is-hidden').addClass('bookmarked');
                        $this.removeClass('un-bookmarked').addClass('bookmarked');
                    },
                    error: function() {
                        this.errorMessageView.showMessage(that.errorMessage, that.errorIcon);
                    },
                    complete: function () {
                        $this.attr("disabled", false).removeClass('is-disabled');
                        that.inProgressView.hideMessage();
                    }
                });
            },

            removeBookmark: function($this, usageId) {
                var deleteUrl = $this.data('url') + $this.data('username') + ',' + usageId;
                var that = this;
                $.ajax({
                    type: "DELETE",
                    url: deleteUrl,
                    success: function () {
                        $('.seq-book.active').find('.bookmark-icon').removeClass('bookmarked').addClass('is-hidden');
                        $this.removeClass('bookmarked').addClass('un-bookmarked');
                    },
                    error: function() {
                        this.errorMessageView.showMessage(that.errorMessage, that.errorIcon);
                    },
                    complete: function (jqXHR, textStatus, errorThrown) {
                        $this.attr("disabled", false).removeClass('is-disabled');
                        that.inProgressView.hideMessage();
                    }
                });
            }
        });
    });
}).call(this, define || RequireJS.define);
