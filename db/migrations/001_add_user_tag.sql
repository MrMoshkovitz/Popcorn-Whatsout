ALTER TABLE titles ADD COLUMN user_tag TEXT DEFAULT 'both' CHECK(user_tag IN ('me', 'wife', 'both'));
