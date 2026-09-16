-- Le référentiel (sites, actifs, signaux, affectation_capteur) est restauré
-- par le parcours amont depuis mistral-referentiel.dump. Ce script vérifie
-- les comptages attendus et échoue si l'un d'eux dévie.
DO $$
DECLARE s int; a int; g int; af int;
BEGIN
    SELECT count(*) INTO s  FROM sites;
    SELECT count(*) INTO a  FROM actifs;
    SELECT count(*) INTO g  FROM signaux;
    SELECT count(*) INTO af FROM affectation_capteur;
    IF (s, a, g, af) IS DISTINCT FROM (4, 46, 25, 490) THEN
        RAISE EXCEPTION 'référentiel inattendu : % sites, % actifs, % signaux, % affectations (attendu 4/46/25/490)', s, a, g, af;
    END IF;
    RAISE NOTICE 'référentiel conforme : 4 sites, 46 actifs, 25 signaux, 490 affectations';
END $$;
