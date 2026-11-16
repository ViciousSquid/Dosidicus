"""How the squid looks: its images and animation frames, its tint, and the
small icons shown above its head.
"""
import os
import random
from PyQt5 import QtCore, QtGui, QtWidgets
from .image_cache import ImageCache


class SquidSpriteMixin:
    """Part of Squid (see squid.py); not used on its own."""

    def apply_tint(self, color):
        """Squid can change colour!"""
        self.tint_color = color
        self.update_squid_image()

    def set_animation_speed(self, speed):
        self.animation_speed = speed

    def load_images(self):
        """Load images with cache to reduce memory usage and apply resolution scaling"""
        from .display_scaling import DisplayScaling
        
        # 70% on a 1080p screen, measured in real pixels; in points on a
        # Retina Mac (DisplayScaling.squid_scale).
        image_scale = DisplayScaling.squid_scale()
        
        # Load original images from cache
        original_images = {
            "left1": ImageCache.get_pixmap(os.path.join("images", "left1.png")),
            "left2": ImageCache.get_pixmap(os.path.join("images", "left2.png")),
            "right1": ImageCache.get_pixmap(os.path.join("images", "right1.png")),
            "right2": ImageCache.get_pixmap(os.path.join("images", "right2.png")),
            "up1": ImageCache.get_pixmap(os.path.join("images", "up1.png")),
            "up2": ImageCache.get_pixmap(os.path.join("images", "up2.png")),
            "sleep1": ImageCache.get_pixmap(os.path.join("images", "sleep1.png")),
            "sleep2": ImageCache.get_pixmap(os.path.join("images", "sleep2.png")),
        }
        
        # Store original dimensions for reference
        self.original_width = original_images["left1"].width()
        self.original_height = original_images["left1"].height()
        
        # Scale images for current resolution
        self.images = {}
        for name, pixmap in original_images.items():
            # Calculate scaled size
            scaled_width = int(pixmap.width() * image_scale)
            scaled_height = int(pixmap.height() * image_scale)
            
            # Create scaled pixmap
            self.images[name] = pixmap.scaled(
                scaled_width, scaled_height,
                QtCore.Qt.KeepAspectRatio, 
                QtCore.Qt.SmoothTransformation
            )
        
        # Scale startled image
        original_startled = ImageCache.get_pixmap(os.path.join("images", "startled.png"))
        startled_width = int(original_startled.width() * image_scale)
        startled_height = int(original_startled.height() * image_scale)
        self.startled_image = original_startled.scaled(
            startled_width, startled_height,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )

        # Scale neurogenesis icon image
        original_ng = ImageCache.get_pixmap(os.path.join("images", "ng.png"))
        ng_width = int(original_ng.width() * image_scale)
        ng_height = int(original_ng.height() * image_scale)
        self.ng_image = original_ng.scaled(
            ng_width, ng_height,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
        # The height the mental-state icons (sick, curious...) are drawn at:
        # full size, in points. They are pinned by their top edge, so the ng
        # icon - scaled with the squid, 70% on a 1080p screen - is dropped by
        # the difference to put its bottom edge where theirs is.
        self.head_icon_height = DisplayScaling.points(original_ng.height())
        
        # Update squid dimensions to match scaled size
        self.squid_width = self.images["left1"].width()
        self.squid_height = self.images["left1"].height()
        
        print(f"Squid scaled to {self.squid_width}x{self.squid_height} pixels")

    def show_startled_icon(self):
        """Show the startled icon above the squid's head"""
        if self.startled_icon is None:
            self.startled_icon = QtWidgets.QGraphicsPixmapItem(self.startled_image)
            self.startled_icon.setZValue(500)  # Below DIRTY text (z=1000) but above decorations
            self.ui.scene.addItem(self.startled_icon)
        self.update_startled_icon_position()

    def hide_startled_icon(self):
        """Remove the startled icon"""
        if self.startled_icon is not None:
            self.ui.scene.removeItem(self.startled_icon)
            self.startled_icon = None
            self.place_head_icon()          # whichever icon was waiting takes its place

    def show_neurogenesis_icon(self):
        """Show the neurogenesis (ng.png) icon above the squid's head"""
        if self.ng_icon is None:
            self.ng_icon = QtWidgets.QGraphicsPixmapItem(self.ng_image)
            self.ng_icon.setZValue(500)  # Below DIRTY text (z=1000) but above decorations
            self.ui.scene.addItem(self.ng_icon)
        self.update_neurogenesis_icon_position()

    def hide_neurogenesis_icon(self):
        """Remove the neurogenesis icon"""
        if self.ng_icon is not None:
            self.ui.scene.removeItem(self.ng_icon)
            self.ng_icon = None
            self.place_head_icon()          # whichever icon was waiting takes its place

    #: The gap between the top of the squid and the bottom of an icon above
    #: its head, in pixels of the tank as designed (drawn at the tank's scale).
    HEAD_ICON_GAP = 10

    def _head_icons(self):
        """Every icon that applies now, most important first: the one shown
        is the first. Neurogenesis always comes first - it is the rarest
        thing a player can see, and it is only there for a few seconds."""
        icons = [getattr(self, 'ng_icon', None), getattr(self, 'sick_icon_item', None),
                 getattr(self, 'startled_icon', None)]
        manager = getattr(self, 'mental_state_manager', None)
        for state in (getattr(manager, 'mental_states', None) or {}).values():
            icons.append(getattr(state, 'icon_item', None))
        seen, found = set(), []
        for icon in icons:
            if icon is not None and id(icon) not in seen:
                seen.add(id(icon))
                found.append(icon)
        return found

    def place_head_icon(self, icon=None):
        """Show ONE icon above the squid's head, just above it - and none
        while the squid itself is out of sight (away visiting another tank).

        Several things can be true of a squid at once (it has just grown a
        neuron and it is curious), and each has an icon. Only one is shown at
        a time: neurogenesis whenever it is there (it lasts a few seconds),
        otherwise the first that applies of sick, startled, then the other
        states (the order of _head_icons). The rest stay hidden until it is
        their turn.

        The icon's bottom edge sits a small gap above the squid, centred on
        it. Icons used to be pinned a fixed 100 pixels above it by their top
        edge - right for a full-size icon on the screen the game was designed
        on, and floating further above the squid the smaller the tank was
        drawn - one on top of another, and some were moved less often than
        the squid, so they trailed behind it.
        """
        from .display_scaling import DisplayScaling
        icons = self._head_icons()
        if icon is not None and all(icon is not other for other in icons):
            icons.append(icon)
        if not icons:
            return
        gap = DisplayScaling.points(self.HEAD_ICON_GAP)
        body = getattr(self, 'squid_item', None)
        in_tank = bool(body.isVisible()) if body is not None else True
        for index, each in enumerate(icons):
            pixmap = each.pixmap()
            each.setPos(int(round(self.squid_x + self.squid_width / 2.0 - pixmap.width() / 2.0)),
                        self.squid_y - gap - pixmap.height())
            each.setVisible(in_tank and index == 0)     # the first, and only it

    def set_in_tank(self, present):
        """Show or hide the squid's body - and with it everything drawn
        above its head. A squid that swam out left its icons hanging in the
        water where it had been."""
        body = getattr(self, 'squid_item', None)
        if body is not None:
            body.setVisible(bool(present))
        self.update_head_icon_positions()
        manager = getattr(self, 'mental_state_manager', None)
        if manager is not None:
            manager.update_positions()

    def update_neurogenesis_icon_position(self):
        """Position the neurogenesis icon above the squid"""
        self.place_head_icon(self.ng_icon)

    def update_startled_icon_position(self):
        """Position the startled icon above the squid"""
        self.place_head_icon(self.startled_icon)

    def update_head_icon_positions(self):
        """Re-pin every head-mounted icon to the squid's head.

        The sick, startled and neurogenesis icons are all separate scene items
        drawn at an offset from the squid rather than children of it, so each
        one has to be moved every time the squid moves. Only the sick icon was
        being moved, so the other two stayed floating wherever the squid
        happened to be standing when they appeared and never caught up.
        """
        # getattr guards: the icon attributes are set in __init__, but this runs
        # from move_squid, which tests and headless runs drive against a squid
        # built without the graphics attributes.
        self.place_head_icon()       # all of them, together (see there)

    def load_poop_images(self):
        from .display_scaling import DisplayScaling
        self.poop_images = [
            DisplayScaling.to_points(QtGui.QPixmap(os.path.join("images", "poop1.png"))),
            DisplayScaling.to_points(QtGui.QPixmap(os.path.join("images", "poop2.png")))
        ]
        self.poop_width = self.poop_images[0].width()
        self.poop_height = self.poop_images[0].height()

    def show_eating_effect(self):
        if not self.is_debug_mode():
            return

        effect_item = QtWidgets.QGraphicsEllipseItem(self.squid_x, self.squid_y, self.squid_width, self.squid_height)
        effect_item.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 0, 100)))
        effect_item.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        self.ui.scene.addItem(effect_item)

        opacity_effect = QtWidgets.QGraphicsOpacityEffect()
        effect_item.setGraphicsEffect(opacity_effect)

        self.eating_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
        self.eating_animation.setDuration(1000)
        self.eating_animation.setStartValue(2.5)
        self.eating_animation.setEndValue(0.0)
        self.eating_animation.setEasingCurve(QtCore.QEasingCurve.InQuad)

        self.eating_animation.finished.connect(lambda: self.ui.scene.removeItem(effect_item))

        self.eating_animation.start()

    def change_to_rps_image(self):
        from .display_scaling import DisplayScaling
        self.rps_image = DisplayScaling.to_points(
            QtGui.QPixmap(os.path.join("images", "squid_rps_frame.png")))
        self.squid_item.setPixmap(self.rps_image)

    def restore_normal_image(self):
        self.squid_item.setPixmap(self.current_image())

    def update_squid_image(self):
        self.squid_item.setPixmap(self.current_image())

    def current_image(self):
        """
        Return the current image of the squid, with tint applied using
        CompositionMode_SourceAtop to tint all non-transparent pixels.
        """
        # 1. Select the base image based on status/direction
        if hasattr(self, 'startled_transition') and self.startled_transition:
            base_image = self.startled_image
        elif hasattr(self, 'status') and self.status == "startled" and not self.is_sleeping:
            direction = "left" if random.random() < 0.5 else "right"
            base_image = self.images[f"{direction}{self.current_frame + 1}"]
        elif self.is_sleeping:
            base_image = self.images[f"sleep{self.current_frame + 1}"]
        elif self.squid_direction == "left":
            base_image = self.images[f"left{self.current_frame + 1}"]
        elif self.squid_direction == "right":
            base_image = self.images[f"right{self.current_frame + 1}"]
        elif self.squid_direction == "up":
            base_image = self.images[f"up{self.current_frame + 1}"]
        else:
            base_image = self.images["left1"]

        # 2. Washed with its colour, if the player gave it one - drawn the
        #    same way in every tank it is ever seen in (src/tint.py).
        if not self.tint_color:
            return base_image
        from .tint import tinted
        return tinted(base_image, self.tint_color)

    def show_sick_icon(self):
        if self.sick_icon_item is None:
            from .display_scaling import DisplayScaling
            sick_icon_pixmap = DisplayScaling.to_points(
                QtGui.QPixmap(os.path.join("images", "sick.png")))
            self.sick_icon_item = QtWidgets.QGraphicsPixmapItem(sick_icon_pixmap)
            self.sick_icon_item.setZValue(500)  # Below DIRTY text (z=1000) but above decorations
            self.ui.scene.addItem(self.sick_icon_item)
        self.update_sick_icon_position()

    def hide_sick_icon(self):
        if self.sick_icon_item is not None:
            self.ui.scene.removeItem(self.sick_icon_item)
            self.sick_icon_item = None

    def update_sick_icon_position(self):
        self.place_head_icon(self.sick_icon_item)
