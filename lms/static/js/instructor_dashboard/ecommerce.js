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
        $( "#coupon_expiration_date" ).datepicker({
            minDate: 0
        });
        var view = new edx.instructor_dashboard.ecommerce.ExpiryCouponView();
        $('input[name="user-enrollment-report"]').click(function(){
            var url = $(this).data('endpoint');
            $.ajax({
             dataType: "json",
             url: url,
             success: function (data) {
                $('#enrollment-report-request-response').text(data['status']);
                return $("#enrollment-report-request-response").css({
                  "display": "block"
                });
               },
             error: function(std_ajax_err) {
                $('#enrollment-report-request-response-error').text(gettext('Error generating grades. Please try again.'));
                return $("#enrollment-report-request-response-error").css({
                  "display": "block"
                });
             }
           });
        });
        $('input[name="exec-summary-report"]').click(function(){
            var url = $(this).data('endpoint');
            $.ajax({
             dataType: "json",
             url: url,
             success: function (data) {
                $("#exec-summary-report-request-response").text(data['status']);
                return $("#exec-summary-report-request-response").css({
                  "display": "block"
                });
               },
             error: function(std_ajax_err) {
                $('#exec-summary-report-request-response-error').text(gettext('Error generating grades. Please try again.'));
                return $("#exec-summary-report-request-response-error").css({
                  "display": "block"
                });
             }
           });
        });
    });
})(Backbone, $, _, gettext);