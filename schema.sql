BEGIN;
--
-- Create model Car
--
CREATE TABLE "cars_car" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(100) NOT NULL, "color" varchar(30) NOT NULL, "position" bigint NOT NULL);
CREATE INDEX "car_color_pos_idx" ON "cars_car" ("color", "position");
CREATE INDEX "car_pos_idx" ON "cars_car" ("position");
COMMIT;
