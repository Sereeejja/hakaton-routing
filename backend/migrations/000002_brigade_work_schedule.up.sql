ALTER TABLE brigades
ADD COLUMN work_schedule text NOT NULL DEFAULT '2/2'
CHECK (work_schedule IN ('2/2', '5/2'));
