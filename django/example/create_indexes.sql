/**
 * Create the full text search indexes with a postgresql database
 */

BEGIN;

/** Cell Table **/

alter table example_cell add column search_vector tsvector;

create trigger tsvectorupdate 
	BEFORE INSERT OR UPDATE ON example_cell 
	FOR EACH ROW EXECUTE PROCEDURE 
	tsvector_update_trigger(search_vector, 'pg_catalog.english', facility_id,name,clo_id,alternate_name,alternate_id,center_name,center_specific_id);
	
/** follows is only necessary if updating an already filled table **/
update example_cell set search_vector = to_tsvector('pg_catalog.english',
	coalesce(facility_id,'') || ' ' || coalesce(name,'') || ' ' || coalesce(clo_id,'') || ' ' || 
	coalesce(alternate_name,'') || ' ' ||	coalesce(alternate_id,'') || ' ' || coalesce(center_name,'') || ' ' || coalesce(center_specific_id,''));		

create index example_cell_index on example_cell using gin(search_vector);

/** Small Molecule Table **/

alter table example_smallmolecule add column search_vector tsvector;

create trigger tsvectorupdate 
	BEFORE INSERT OR UPDATE ON example_smallmolecule 
	FOR EACH ROW EXECUTE PROCEDURE 
	tsvector_update_trigger(search_vector, 'pg_catalog.english', facility_id,name,alternate_names);
	
/** follows is only necessary if updating an already filled table **/
update example_smallmolecule set search_vector = to_tsvector('pg_catalog.english',
	coalesce(facility_id,'') || ' ' || coalesce(name,'') || ' ' || coalesce(alternate_names,'') );		

create index example_smallmolecule_index on example_smallmolecule using gin(search_vector);

COMMIT;
