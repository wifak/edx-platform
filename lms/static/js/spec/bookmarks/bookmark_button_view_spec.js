define(['backbone', 'jquery', 'underscore', 'js/common_helpers/ajax_helpers', 'js/common_helpers/template_helpers',
        'js/bookmarks/views/bookmark_button'
       ],
    function (Backbone, $, _, AjaxHelpers, TemplateHelpers, BookmarkButtonView) {
        'use strict';

        describe("bookmarks.button", function () {

            var bookmarkButtonView;

            beforeEach(function () {
                loadFixtures('js/fixtures/bookmarks/bookmark_button.html');
                TemplateHelpers.installTemplates(
                    [
                        'templates/fields/message_banner'
                    ]
                );
            });

            var setBookmarkButtonView = function(isBookmarked) {
                bookmarkButtonView = new BookmarkButtonView({el: '.xblock-student_view-vertical', bookmarked: isBookmarked});
            };

            var verifyBookmarkButtonState = function (bookmarked) {
                var $bookmarkButton = bookmarkButtonView.$('.bookmark-button');
                if (bookmarked) {
                    expect($bookmarkButton).toHaveAttr('aria-pressed', 'true');
                    expect($bookmarkButton).toHaveClass('bookmarked');
                    expect($bookmarkButton.find('.bookmark-sr').text()).toBe('Click to remove');
                } else {
                    expect($bookmarkButton).toHaveAttr('aria-pressed', 'false');
                    expect($bookmarkButton).toHaveClass('un-bookmarked');
                    expect($bookmarkButton.find('.bookmark-sr').text()).toBe('Click to add');
                }
                expect($bookmarkButton.data('bookmarkId')).toBe('testuser,usage_1');
            };

            it("rendered correctly ", function () {
                setBookmarkButtonView(false);
                verifyBookmarkButtonState(false);
            });

            it("bookmark the block correctly", function () {
                var requests = AjaxHelpers.requests(this);
                setBookmarkButtonView(false);
                verifyBookmarkButtonState(false);

                var $bookmarkButton = bookmarkButtonView.$('.bookmark-button');
                spyOn(bookmarkButtonView, 'addBookmark').andCallThrough();
                spyOnEvent($bookmarkButton, 'bookmark:add');

                $bookmarkButton.click();

                var flag;
                runs(function () {
                    flag = false;

                    setTimeout(function () {
                        flag = true;
                    }, 50);
                });
                waitsFor(function () {
                    return flag;
                }, "The block should be bookmarked.");
                runs(function () {
                    expect(bookmarkButtonView.addBookmark).toHaveBeenCalled();
                    AjaxHelpers.respondWithJson(requests, {});
                    verifyBookmarkButtonState(true);
                    expect('bookmark:add').toHaveBeenTriggeredOn($bookmarkButton);
                });
            });

            it("un-bookmark the block correctly", function() {
                var requests = AjaxHelpers.requests(this);
                setBookmarkButtonView(true);
                verifyBookmarkButtonState(true);

                var $bookmarkButton = bookmarkButtonView.$('.bookmark-button');
                spyOn(bookmarkButtonView, 'removeBookmark').andCallThrough();
                spyOnEvent($bookmarkButton, 'bookmark:remove');

                $bookmarkButton.click();

                var flag;
                runs(function() {
                    flag = false;

                    setTimeout(function() {
                        flag = true;
                    }, 50);
                });
                waitsFor(function() {
                    return flag;
                }, "The block should be un-bookmarked.");
                runs(function() {
                    expect(bookmarkButtonView.removeBookmark).toHaveBeenCalled();
                    AjaxHelpers.respondWithJson(requests, {});
                    verifyBookmarkButtonState(false);
                    expect('bookmark:remove').toHaveBeenTriggeredOn($bookmarkButton);
                });
            });

            it("shows an error message for HTTP 500", function () {
                var requests = AjaxHelpers.requests(this),
                    $messageBanner = $('.coursewide-message-banner');
                setBookmarkButtonView(false);
                bookmarkButtonView.$('.bookmark-button').click();

                AjaxHelpers.respondWithError(requests);

                expect($messageBanner.text().trim()).toBe(bookmarkButtonView.errorMessage);

                // For bookmarked button.
                setBookmarkButtonView(true);
                bookmarkButtonView.$('.bookmark-button').click();

                AjaxHelpers.respondWithError(requests);

                expect($messageBanner.text().trim()).toBe(bookmarkButtonView.errorMessage);
            });

        });
    });
