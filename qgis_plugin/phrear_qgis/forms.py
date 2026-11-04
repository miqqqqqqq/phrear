"""Attribute forms, relations and styles of the project layers, from the schema.

The plans come from ``client.forms``; this module only applies them to QGIS.
Everything set here is saved with the QGIS project.
"""

from __future__ import annotations

import html
from typing import Any

from qgis.core import (
    Qgis,
    QgsAttributeEditorContainer,
    QgsAttributeEditorField,
    QgsAttributeEditorRelation,
    QgsAttributeEditorTextElement,
    QgsDefaultValue,
    QgsEditorWidgetSetup,
    QgsExpressionContextUtils,
    QgsFieldConstraints,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsPolymorphicRelation,
    QgsProject,
    QgsRelation,
    QgsSingleSymbolRenderer,
    QgsValueMapFieldFormatter,
)

from .client.forms import (
    TABLE_VARIABLE,
    FieldPlan,
    FormPlan,
    RelationPlan,
    display_expression,
    form_plans,
    relation_plans,
    styles,
    symbol_properties,
)
from .i18n import tr

Layers = dict[str, Any]
"""Vector layers of one project by table name."""

_SYMBOLS = {"marker": QgsMarkerSymbol, "line": QgsLineSymbol, "fill": QgsFillSymbol}


def configure(layers: Layers, schema: dict[str, Any], lang: str, root: str) -> list[str]:
    """Styles, fields, relations and form layouts of a freshly loaded project.

    Returns the names of the relations that QGIS rejected (none expected).
    """
    project_doc = schema["project"]
    plans = form_plans(schema, lang)
    tables = {t["name"]: t for t in project_doc["tables"]}
    for table, layer in layers.items():
        QgsExpressionContextUtils.setLayerVariable(layer, TABLE_VARIABLE, table)
        style = styles(schema).get(table)
        if style is not None and layer.isSpatial():
            apply_style(layer, style)
        if table in plans:
            apply_fields(layer, plans[table], layers)
            expression = display_expression(tables[table], project_doc.get("relations", []))
            if expression:
                layer.setDisplayExpression(expression)
    relations, rejected = add_relations(relation_plans(schema, lang, root), layers)
    for table, layer in layers.items():
        if table in plans:
            apply_layout(layer, plans[table], relations.get(table, []))
    return rejected


# --- styles ---------------------------------------------------------------------------


def apply_style(layer: Any, style: dict[str, Any]) -> None:
    kind, properties = symbol_properties(style)
    symbol = _SYMBOLS[kind].createSimple(properties)
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.triggerRepaint()


# --- fields ---------------------------------------------------------------------------


def _widget_setup(plan: FieldPlan, layers: Layers) -> QgsEditorWidgetSetup:
    widget = plan.widget
    config = dict(widget.config)
    if widget.type == "ValueMap":
        config["map"] = [{tr("(empty)"): QgsValueMapFieldFormatter.NULL_VALUE}, *config["map"]]
    if widget.type == "ValueRelation":
        target = layers.get(widget.lookup_table or "")
        if target is None:
            return QgsEditorWidgetSetup("TextEdit", {"IsMultiline": False, "UseHtml": False})
        config.update(
            {
                "Layer": target.id(),
                "LayerName": target.name(),
                "LayerSource": target.publicSource(),
                "LayerProviderName": target.providerType(),
            }
        )
    return QgsEditorWidgetSetup(widget.type, config)


def _range_text(plan: FieldPlan) -> str:
    if plan.minimum is not None and plan.maximum is not None:
        return tr("Expected between {minimum} and {maximum}.").format(
            minimum=plan.minimum, maximum=plan.maximum
        )
    if plan.minimum is not None:
        return tr("Expected at least {minimum}.").format(minimum=plan.minimum)
    return tr("Expected at most {maximum}.").format(maximum=plan.maximum)


def apply_fields(layer: Any, form: FormPlan, layers: Layers) -> None:
    """Alias, editor widget, constraints and default of every field of the schema.

    Required and unique fields are hard constraints (the feature cannot be saved);
    a value outside the schema range is a soft one (a warning in the form). The
    core checks both again.
    """
    hard = QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
    soft = QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft
    fields = layer.fields()
    for plan in form.fields:
        index = fields.indexFromName(plan.name)
        if index < 0:
            continue
        layer.setFieldAlias(index, plan.alias)
        layer.setEditorWidgetSetup(index, _widget_setup(plan, layers))
        if plan.required:
            layer.setFieldConstraint(index, QgsFieldConstraints.Constraint.ConstraintNotNull, hard)
        if plan.unique:
            layer.setFieldConstraint(index, QgsFieldConstraints.Constraint.ConstraintUnique, hard)
        expression = plan.range_expression
        if expression:
            layer.setConstraintExpression(index, expression, _range_text(plan))
            layer.setFieldConstraint(
                index, QgsFieldConstraints.Constraint.ConstraintExpression, soft
            )
        if plan.default is not None:
            layer.setDefaultValueDefinition(index, QgsDefaultValue(plan.default, False))


# --- relations ------------------------------------------------------------------------


def _remove_existing(manager: Any, relation_id: str) -> None:
    if manager.polymorphicRelation(relation_id).isValid():
        manager.removePolymorphicRelation(relation_id)
    if manager.relation(relation_id).isValid():
        manager.removeRelation(relation_id)


def add_relations(
    plans: list[RelationPlan], layers: Layers
) -> tuple[dict[str, list[tuple[Any, str]]], list[str]]:
    """Add the relations to the QGIS project.

    Returns, by parent table, the relations with the label of their editor, and
    the names of the relations that QGIS found invalid. Children belong to their
    parent (composition): deleting a parent in QGIS deletes them too, after
    QGIS asks for confirmation.
    """
    manager = QgsProject.instance().relationManager()
    composition = Qgis.RelationshipStrength.Composition
    by_parent: dict[str, list[tuple[Any, str]]] = {}
    rejected: list[str] = []
    for plan in plans:
        child = layers.get(plan.child)
        parents = [layers[p] for p in plan.parents if p in layers]
        if child is None or len(parents) != len(plan.parents):
            rejected.append(plan.name)
            continue
        _remove_existing(manager, plan.id)
        if plan.polymorphic:
            poly = QgsPolymorphicRelation()
            poly.setId(plan.id)
            poly.setName(plan.name)
            poly.setReferencingLayer(child.id())
            poly.addFieldPair(plan.child_field, plan.parent_field)
            poly.setReferencedLayerField(plan.layer_field or "")
            poly.setReferencedLayerExpression(plan.layer_expression or "")
            poly.setReferencedLayerIds([p.id() for p in parents])
            poly.setRelationStrength(composition)
            if not poly.isValid():
                rejected.append(plan.name)
                continue
            manager.addPolymorphicRelation(poly)
            for table, parent in zip(plan.parents, parents, strict=True):
                for relation in manager.referencedRelations(parent):
                    if relation.polymorphicRelationId() == plan.id:
                        by_parent.setdefault(table, []).append((relation, plan.label))
        else:
            relation = QgsRelation()
            relation.setId(plan.id)
            relation.setName(plan.name)
            relation.setReferencingLayer(child.id())
            relation.setReferencedLayer(parents[0].id())
            relation.addFieldPair(plan.child_field, plan.parent_field)
            relation.setStrength(composition)
            if not relation.isValid():
                rejected.append(plan.name)
                continue
            manager.addRelation(relation)
            by_parent.setdefault(plan.parents[0], []).append((relation, plan.label))
    return by_parent, rejected


# --- form layout ----------------------------------------------------------------------


def help_html(form: FormPlan) -> str:
    def escape(text: str) -> str:
        return html.escape(text, quote=False)

    lines = [escape(form.help)] if form.help else []
    lines += [f"<b>{escape(p.alias)}</b>: {escape(p.help)}" for p in form.fields if p.help]
    # ``[%`` would start an expression in a text element of the form.
    return "<br>".join(lines).replace("[%", "[ %")


def apply_layout(layer: Any, form: FormPlan, relations: list[tuple[Any, str]]) -> None:
    """Fields in the order of the plan, the relation editors, then a closed help box."""
    config = layer.editFormConfig()
    config.setLayout(Qgis.AttributeFormLayout.DragAndDrop)
    root = config.invisibleRootContainer()
    root.clear()
    fields = layer.fields()
    fid = fields.indexFromName("fid")
    if fid >= 0:
        root.addChildElement(QgsAttributeEditorField("fid", fid, root))
    for plan in form.fields:
        index = fields.indexFromName(plan.name)
        if index < 0:
            continue
        root.addChildElement(QgsAttributeEditorField(plan.name, index, root))
        config.setReadOnly(index, plan.read_only)
    for relation, label in relations:
        element = QgsAttributeEditorRelation(relation, root)
        # Without an explicit type QGIS looks for a "basic" widget that no longer exists.
        element.setRelationWidgetTypeId("relation_editor")
        element.setLabel(label)
        element.setShowLabel(True)
        root.addChildElement(element)
    text = help_html(form)
    if text:
        box = QgsAttributeEditorContainer(tr("Help"), root)
        box.setType(Qgis.AttributeEditorContainerType.GroupBox)
        box.setCollapsed(True)
        element = QgsAttributeEditorTextElement(tr("Help"), box)
        element.setText(text)
        element.setShowLabel(False)
        box.addChildElement(element)
        root.addChildElement(box)
    layer.setEditFormConfig(config)
