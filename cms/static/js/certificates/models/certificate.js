// Backbone.js Application Model: Certificate

define([ // jshint ignore:line
    'underscore',
    'underscore.string',
    'backbone',
    'backbone-relational',
    'backbone.associations',
    'gettext',
    'coffee/src/main',
    'js/certificates/models/signatory',
    'js/certificates/collections/signatories'
],
function (_, str, Backbone, BackboneRelational, BackboneAssociations, gettext, CoffeeSrcMain,
          SignatoryModel, SignatoryCollection) {
    'use strict';
    _.str = str;
    var Certificate = Backbone.RelationalModel.extend({
        idAttribute: "id",
        defaults: {
            name: 'Name of the certificate',
            description: 'Description of the certificate',
            course_title: 'Title of the course',
            org_logo_path: '',
            version: 1,
            is_active: false
        },

        // Certificate child collection/model mappings (backbone-relational)
        relations: [{
            type: Backbone.HasMany,
            key: 'signatories',
            relatedModel: SignatoryModel,
            collectionType: SignatoryCollection,
            reverseRelation: {
                key: 'certificate',
                includeInJSON: "id"
            }
        }],

        initialize: function(attributes, options) {
            // Set up the initial state of the attributes set for this model instance
            this.canBeEmpty = options && options.canBeEmpty;
            if(options.add) {
                // Ensure at least one child Signatory model is defined for any new Certificate model
                attributes.signatories = new SignatoryModel({certificate: this});
            }
            this.setOriginalAttributes();
            return this;
        },

        parse: function (response) {
            // Parse must be defined for the model, but does not need to do anything special right now
            return response;
        },

        setOriginalAttributes: function() {
            // Remember the current state of this model (enables edit->cancel use cases)
            this._originalAttributes = this.parse(this.toJSON());

            // If no url is defined for the signatories child collection we'll need to create that here as well
            if(!this.isNew() && !this.get('signatories').url) {
                this.get('signatories').url = this.collection.url + '/' + this.get('id') + '/signatories';
            }
        },

        validate: function(attrs) {
            // Ensure the provided attributes set meets our expectations for format, type, etc.
            if (!_.str.trim(attrs.name)) {
                return {
                    message: gettext('Certificate name is required.'),
                    attributes: {name: true}
                };
            }
            var all_signatories_valid  = _.every(attrs.signatories.models, function(signatory){
                return signatory.isValid();
            });
            if (!all_signatories_valid) {
                return {
                    message: gettext('Signatory field(s) has invalid data.'),
                    attributes: {signatories: attrs.signatories.models}
                };
            }
        },

        reset: function() {
            // Revert the attributes of this model instance back to initial state
            this.set(this._originalAttributes, { parse: true, validate: true });
        }
    });
    return Certificate;
});
