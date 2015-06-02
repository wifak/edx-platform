var edx = edx || {};

(function(Backbone, $, _, gettext) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.ecommerce = {};

    edx.instructor_dashboard.ecommerce.ExpiryCouponView = Backbone.View.extend({
        el: 'li#add-coupon-modal-field-expiry',
        events: {
            'click input[type="checkbox"]': 'clicked'
        },
        initialize: function() {
            $('li#add-coupon-modal-field-expiry input[name="expiration_date"]').hide();
            _.bindAll(this, 'clicked');
        },
        clicked: function (event) {
            if (event.currentTarget.checked) {
                this.$el.find('#coupon_expiration_date').show();
                this.$el.find('#coupon_expiration_date').focus();
            }
            else {
                this.$el.find('#coupon_expiration_date').hide();
            }
        }
    });

    $(function() {
        var registration_code_status_form = $("form#set_regcode_status_form");
        var lookup_button = $('#set_regcode_status_form input#lookup_regcode');
        var registration_code_status_form_error = $('#set_regcode_status_form #regcode_status_form_error');
        var registration_code_status_form_success = $('#set_regcode_status_form #regcode_status_form_success');

        $( "#coupon_expiration_date" ).datepicker({
            minDate: 0
        });
        var view = new edx.instructor_dashboard.ecommerce.ExpiryCouponView();
        var request_response = $('.reports .request-response');
        var request_response_error = $('.reports .request-response-error');
        $('input[name="user-enrollment-report"]').click(function(){
            var url = $(this).data('endpoint');
            $.ajax({
             dataType: "json",
             url: url,
             success: function (data) {
                request_response.text(data['status']);
                return $(".reports .msg-confirm").css({
                  "display": "block"
                });
             },
             error: function(std_ajax_err) {
                request_response_error.text(gettext('Error generating grades. Please try again.'));
                return $(".reports .msg-error").css({
                  "display": "block"
                });
             }
           });
        });

        String.prototype.capitalizeFirstLetter = function() {
            return this.charAt(0).toUpperCase() + this.slice(1);
        };
        lookup_button.click(function () {
            registration_code_status_form_error.attr('style', 'display: none');

            lookup_button.attr('disabled', true);
            var url = $(this).data('endpoint');
            var lookup_registration_code = $('#set_regcode_status_form input[name="regcode_code"]').val();
            if (lookup_registration_code == '') {
                registration_code_status_form_error.attr('style', 'display: block !important');
                registration_code_status_form_error.text(gettext('Please enter the Registration Code.'));
                lookup_button.removeAttr('disabled');
                return false;
            }
            $.ajax({
                type: "POST",
                data: {
                    "registration_code"  : lookup_registration_code
                },
                url: url,
                success: function (data) {
                    lookup_button.removeAttr('disabled');
                    if (data.is_registration_code_exists == 'false') {
                        registration_code_status_form_error.attr('style', 'display: none');
                        registration_code_status_form_error.attr('style', 'display: block !important');
                        registration_code_status_form_error.text(gettext(data.message));
                    }
                    else {
                        var is_registration_code_valid = data.is_registration_code_valid.toString().capitalizeFirstLetter();
                        var is_registration_code_redeemed = data.is_registration_code_redeemed.toString().capitalizeFirstLetter();
                        var actions_links = '';
                        var actions = [];
                        if (is_registration_code_valid == 'True') {
                            actions.push(
                                {
                                    'action_url': data.registration_code_detail_url,
                                    'action_name': 'Mark as Invalid',
                                    'registration_code': lookup_registration_code,
                                    'action_type': 'invalidate_registration_code'
                                }
                            );
                        }
                        else {
                            actions.push(
                                {
                                    'action_url': data.registration_code_detail_url,
                                    'action_name': 'Mark as Valid',
                                    'registration_code': lookup_registration_code,
                                    'action_type': 'validate_registration_code'
                                }
                            );
                        }
                        if (is_registration_code_redeemed == 'True') {
                            actions.push(
                                {
                                    'action_url': data.registration_code_detail_url,
                                    'action_name': 'Mark as UnRedeem',
                                    'registration_code': lookup_registration_code,
                                    'action_type': 'unredeem_registration_code'
                                }
                            );
                        }

                        for ( var i = 0; i < actions.length; i++ ) {
                            actions_links += '<a class="registration_code_action_link" data-registration-code="'+
                            actions[i]["registration_code"] +'" data-action-type="'+ actions[i]["action_type"] +'"' +
                            ' href="#" data-endpoint="' + actions[i]["action_url"] +'">' +
                            actions[i]["action_name"] + '</a>';
                        }
                        var registration_code_lookup_actions = $('<table width="100%" class="tb_registration_code_status">' +
                            '<thead> <th width="15%">' + gettext('Code') + '</th> <th width="20%">'+ gettext('Redeemed') + '</th>'+
                            '<th width="14%">' + gettext('Valid') + '</th> <th>' + gettext('Actions') + '</th></thead><tbody><tr>'+
                            '<td>' + lookup_registration_code + '</td>' +
                            '<td>' + is_registration_code_redeemed +'</td>' +
                            '<td>' + is_registration_code_valid + '</td><td>' +
                            actions_links +
                            '</td></tr> </tbody> </table>'
                        );
                        // before insertAfter do this.
                        // remove the first element after the registration_code_status_form
                        // so it doesn't duplicate the registration_code_lookup_actions in the UI.
                        registration_code_status_form.next().remove();

                        registration_code_lookup_actions.insertAfter(registration_code_status_form);
                    }
                },
                error: function(jqXHR, textStatus, errorThrown) {
                    var data = $.parseJSON(jqXHR.responseText);
                    registration_code_status_form_error.attr('style', 'display: none');
                    lookup_button.removeAttr('disabled');
                    registration_code_status_form_error.attr('style', 'display: block !important');
                    registration_code_status_form_error.text(gettext(data.message));
                }
            });
        });
        $("section#invalidate_registration_code_modal").on('click', 'a.registration_code_action_link', function() {
            event.preventDefault();
            registration_code_status_form_error.attr('style', 'display: none');
            lookup_button.attr('disabled', true);
            var url = $(this).data('endpoint');
            var action_type = $(this).data('action-type');
            var registration_code = $(this).data('registration-code');
            $.ajax({
                type: "POST",
                data: {
                    "registration_code": registration_code,
                    "action_type": action_type
                },
                url: url,
                success: function (data) {
                    $('#set_regcode_status_form input[name="regcode_code"]').val('');
                    registration_code_status_form.next().remove();
                    registration_code_status_form_error.attr('style', 'display: none');
                    registration_code_status_form_success.attr('style', 'display: none');
                    lookup_button.removeAttr('disabled');
                    registration_code_status_form_success.attr('style', 'display: block !important');
                    registration_code_status_form_success.text(gettext(data.message));
                    registration_code_status_form_success.fadeOut(4000 , function(){
                        registration_code_status_form_success.attr('style', 'display: none');
                        registration_code_status_form_success.text('');
                        registration_code_status_form_success.hide();
                    });
                },
                error: function(jqXHR, textStatus, errorThrown) {
                    var data = $.parseJSON(jqXHR.responseText);
                    registration_code_status_form_error.attr('style', 'display: none');
                    lookup_button.removeAttr('disabled');
                    registration_code_status_form_error.attr('style', 'display: block !important');
                    registration_code_status_form_error.text(gettext(data.message));
                }
            })
        });
    });
})(Backbone, $, _, gettext);