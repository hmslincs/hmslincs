/**
 * Create the full text search indexes with a postgresql database
 **/

/** TODO: generate the index definitions automatically from the django model definitions **/

BEGIN;

/** Cell Table **/
alter table example_cell drop column if exists search_vector;
alter table example_cell add column search_vector tsvector;

drop trigger if exists tsvectorupdate on example_cell;
create trigger tsvectorupdate 
	BEFORE INSERT OR UPDATE ON example_cell 
	FOR EACH ROW EXECUTE PROCEDURE 
			tsvector_update_trigger(search_vector, 'pg_catalog.english', facility_id,cl_name,cl_id,cl_alternate_name,cl_alternate_id,cl_center_name,cl_center_specific_id,assay,
			cl_provider_name,cl_provider_catalog_id,cl_batch_id,cl_organism,cl_organ,cl_tissue,cl_cell_type,cl_cell_type_detail,cl_disease,cl_disease_detail,
			cl_growth_properties,cl_genetic_modification,cl_related_projects,cl_recommended_culture_conditions);
/**
 	what to do with numeric fields: mgh_id,
**/	
/** updating an already filled table **/
update example_cell set search_vector = to_tsvector('pg_catalog.english',
	coalesce(facility_id,'')  || ' ' || coalesce(cl_name,'') || ' ' || coalesce(cl_id,'') || ' ' || coalesce(cl_alternate_name,'') || ' ' || 
	coalesce(cl_alternate_id,'') || ' ' || coalesce(cl_center_name,'') || ' ' || coalesce(cl_center_specific_id,'') || ' ' ||  
	coalesce(assay,'') || ' ' || coalesce(cl_provider_name,'') || ' ' || coalesce(cl_provider_catalog_id,'') || ' ' || coalesce(cl_batch_id,'') || ' ' || 
	coalesce(cl_organism,'') || ' ' || coalesce(cl_organ,'') || ' ' || coalesce(cl_tissue,'') || ' ' || coalesce(cl_cell_type,'') || ' ' || 
	coalesce(cl_cell_type_detail,'') || ' ' || coalesce(cl_disease,'') || ' ' || coalesce(cl_disease_detail,'') || ' ' || 
	coalesce(cl_growth_properties,'') || ' ' || coalesce(cl_genetic_modification,'') || ' ' || coalesce(cl_related_projects,'') || ' ' || 
	coalesce(cl_recommended_culture_conditions)  );
/**
	coalesce(mgh_id,'') || ' ' || 
**/
create index example_cell_index on example_cell using gin(search_vector);

/** Small Molecule Table **/

alter table example_smallmolecule drop column if exists search_vector;
alter table example_smallmolecule add column search_vector tsvector;

drop trigger if exists tsvectorupdate on example_smallmolecule;
create trigger tsvectorupdate 
	BEFORE INSERT OR UPDATE ON example_smallmolecule 
	FOR EACH ROW EXECUTE PROCEDURE 
	tsvector_update_trigger(search_vector, 'pg_catalog.english', facility_id,sm_name,sm_provider,sm_molecular_formula,sm_inchi,sm_smiles);

/**
	TODO: how to index the non-text fields as well?
		sm_pubchem_cid,chembl_id,
**/

/** follows is only necessary if updating an already filled table **/
update example_smallmolecule set search_vector = to_tsvector('pg_catalog.english',
	coalesce(facility_id,'') || ' ' || coalesce(sm_name,'') || ' ' || coalesce(sm_provider,'') || ' ' ||	
	coalesce(sm_molecular_formula,'') || ' ' || coalesce(sm_inchi,'')|| ' ' || coalesce(sm_smiles,''));		

create index example_smallmolecule_index on example_smallmolecule using gin(search_vector);

/** Screen Table **/

alter table example_screen drop column if exists search_vector;
alter table example_screen add column search_vector tsvector;

drop trigger if exists tsvectorupdate on example_screen;
create trigger tsvectorupdate 
	BEFORE INSERT OR UPDATE ON example_screen 
	FOR EACH ROW EXECUTE PROCEDURE 
	tsvector_update_trigger(search_vector, 'pg_catalog.english', facility_id,title,summary,lead_screener_firstname,lead_screener_lastname,lead_screener_email,lab_head_firstname,lab_head_lastname,lab_head_email);

/** follows is only necessary if updating an already filled table **/
update example_screen set search_vector = to_tsvector('pg_catalog.english',
	coalesce(facility_id,'') || ' ' || coalesce(title,'') || ' ' || coalesce(summary,'') || ' ' ||	
	coalesce(lead_screener_firstname,'') || ' ' || coalesce(lead_screener_lastname,'')|| ' ' || coalesce(lead_screener_email,'') || ' ' ||			
	coalesce(lab_head_firstname,'') || ' ' || coalesce(lab_head_lastname,'')|| ' ' || coalesce(lab_head_email,''));		

create index example_screen_index on example_screen using gin(search_vector);

COMMIT;
