')
        
        # Keywords to find context around
        keywords = ['attack', 'threat', 'vulnerability', 'exploit', 'compromise', 
                   'spacecraft', 'satellite', 'ground station']
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            for keyword in keywords:
                if keyword in line_lower:
                    # Get surrounding context
                    start = max(0, i - 2)
                    end = min(len(lines), i + 3)
                    context = ' '.join(lines[start:end])
                    
                    snippets.append({
                        'keyword': keyword,
                        'context': context[:window_size],
                        'line_number': i + 1
                    })
                    
        return snippets[:10]  # Limit to 10 most relevant
        
    def _assess_threat_level(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall threat level based on extracted data"""
        threat_score = 0
        factors = []
        
        # Score based on number of techniques
        tech_count = len(extraction_result['detected_techniques'])
        if tech_count > 0:
            threat_score += tech_count * 10
            factors.append(f"{tech_count} techniques detected")
            
        # Score based on tactics
        tactic_count = len(extraction_result['detected_tactics'])
        if tactic_count > 0:
            threat_score += tactic_count * 5
            factors.append(f"{tactic_count} tactics identified")
            
        # Score based on indicators
        indicator_count = sum(
            len(extraction_result['indicators'][key]) 
            for key in extraction_result['indicators']
        )
        if indicator_count > 0:
            threat_score += indicator_count * 2
            factors.append(f"{indicator_count} indicators found")
            
        # Determine threat level
        if threat_score >= 50:
            level = 'critical'
        elif threat_score >= 30:
            level = 'high'
        elif threat_score >= 15:
            level = 'medium'
        else:
            level = 'low'
            
        return {
            'score': threat_score,
            'level': level,
            'factors': factors
        }
        
    def process_sparta_json(self, json_path: str) -> Dict[str, Any]:
        """Process SPARTA JSON data from ingestion"""
        logger.info(f"Processing SPARTA JSON: {json_path}")
        
        with open(json_path, 'r') as f:
            sparta_data = json.load(f)
            
        # Enhanced processing for full technique coverage
        processed_data = {
            'tactics': {},
            'techniques': {},
            'relationships': [],
            'metadata': sparta_data.get('metadata', {})
        }
        
        # Process tactics
        for tactic in sparta_data.get('tactics', []):
            tactic_id = tactic['id']
            processed_data['tactics'][tactic_id] = {
                'id': tactic_id,
                'name': tactic['name'],
                'description': tactic['description'],
                'techniques': []
            }
            
        # Process techniques with enhanced attributes
        for technique in sparta_data.get('techniques', []):
            tech_id = technique['id']
            
            # Determine actor types based on technique characteristics
            actor_types = self._infer_actor_types(technique)
            
            # Calculate complexity and detection difficulty
            complexity = self._infer_complexity(technique)
            detection = self._infer_detection_difficulty(technique)
            
            processed_technique = {
                'id': tech_id,
                'name': technique['name'],
                'description': technique['description'],
                'severity': technique['severity'],
                'tactic_ids': technique['tactic_ids'],
                'countermeasures': technique.get('countermeasures', []),
                'detection': technique.get('detection', ''),
                'platforms': technique.get('platforms', ['Spacecraft']),
                'data_sources': technique.get('data_sources', []),
                'actor_types': actor_types,
                'complexity': complexity,
                'detection_difficulty': detection,
                'references': technique.get('references', [])
            }
            
            processed_data['techniques'][tech_id] = processed_technique
            
            # Update tactic-technique relationships
            for tactic_id in technique['tactic_ids']:
                if tactic_id in processed_data['tactics']:
                    processed_data['tactics'][tactic_id]['techniques'].append(tech_id)
                    
            # Create relationship entries
            for tactic_id in technique['tactic_ids']:
                processed_data['relationships'].append({
                    'source': tech_id,
                    'target': tactic_id,
                    'type': 'implements_tactic'
                })
                
        # Add coverage statistics
        processed_data['coverage'] = {
            'total_techniques': len(processed_data['techniques']),
            'total_tactics': len(processed_data['tactics']),
            'techniques_per_tactic': {
                tactic_id: len(tactic_data['techniques'])
                for tactic_id, tactic_data in processed_data['tactics'].items()
            }
        }
        
        return processed_data
        
    def _infer_actor_types(self, technique: Dict[str, Any]) -> List[str]:
        """Infer likely actor types for a technique"""
        actor_types = []
        
        desc_lower = technique.get('description', '').lower()
        name_lower = technique.get('name', '').lower()
        
        # Nation state indicators
        if any(term in desc_lower for term in ['advanced', 'sophisticated', 'persistent', 'asat', 'kinetic']):
            actor_types.append('nation_state')
            
        # Criminal indicators
        if any(term in desc_lower for term in ['ransom', 'financial', 'money', 'bitcoin']):
            actor_types.append('criminal')
            
        # Hacktivist indicators
        if any(term in desc_lower for term in ['public', 'embarrass', 'expose', 'leak']):
            actor_types.append('hacktivist')
            
        # Insider indicators
        if any(term in desc_lower for term in ['insider', 'employee', 'contractor', 'authorized']):
            actor_types.append('insider')
            
        # Default to nation state for high-severity techniques
        if not actor_types and technique.get('severity') in ['critical', 'high']:
            actor_types.append('nation_state')
            
        return actor_types or ['unknown']
        
    def _infer_complexity(self, technique: Dict[str, Any]) -> str:
        """Infer exploitation complexity"""
        desc_lower = technique.get('description', '').lower()
        
        if any(term in desc_lower for term in ['simple', 'easy', 'basic', 'readily']):
            return 'low'
        elif any(term in desc_lower for term in ['advanced', 'sophisticated', 'complex', 'difficult']):
            return 'high'
        elif any(term in desc_lower for term in ['extremely', 'highly complex', 'very difficult']):
            return 'very_high'
        else:
            return 'medium'
            
    def _infer_detection_difficulty(self, technique: Dict[str, Any]) -> str:
        """Infer detection difficulty"""
        desc_lower = technique.get('description', '').lower()
        
        if any(term in desc_lower for term in ['obvious', 'easily detected', 'noisy']):
            return 'easy'
        elif any(term in desc_lower for term in ['stealthy', 'covert', 'hidden', 'obfuscated']):
            return 'hard'
        elif any(term in desc_lower for term in ['extremely stealthy', 'undetectable']):
            return 'very_hard'
        else:
            return 'medium'
            
    def export_for_arangodb(self, processed_data: Dict[str, Any], output_path: str):
        """Export processed data in format ready for ArangoDB"""
        arangodb_data = {
            'collections': {
                'tactics': [],
                'techniques': [],
                'actors': [],
                'indicators': []
            },
            'edges': {
                'implements_tactic': [],
                'uses_technique': [],
                'targets_platform': []
            }
        }
        
        # Convert tactics
        for tactic_id, tactic_data in processed_data['tactics'].items():
            arangodb_data['collections']['tactics'].append({
                '_key': tactic_id,
                'name': tactic_data['name'],
                'description': tactic_data['description'],
                'technique_count': len(tactic_data['techniques'])
            })
            
        # Convert techniques
        for tech_id, tech_data in processed_data['techniques'].items():
            arangodb_data['collections']['techniques'].append({
                '_key': tech_id,
                'name': tech_data['name'],
                'description': tech_data['description'],
                'severity': tech_data['severity'],
                'complexity': tech_data['complexity'],
                'detection_difficulty': tech_data['detection_difficulty'],
                'countermeasures': tech_data['countermeasures'],
                'platforms': tech_data['platforms'],
                'actor_types': tech_data['actor_types']
            })
            
            # Create edges
            for tactic_id in tech_data['tactic_ids']:
                arangodb_data['edges']['implements_tactic'].append({
                    '_from': f'techniques/{tech_id}',
                    '_to': f'tactics/{tactic_id}'
                })
                
        # Save ArangoDB-ready data
        with open(output_path, 'w') as f:
            json.dump(arangodb_data, f, indent=2)
            
        logger.info(f"Exported ArangoDB data to {output_path}")
        return arangodb_data


def main():
    """Main extraction process"""
    extractor = SPARTAExtractor()
    
    # Process ingested SPARTA data
    sparta_json = '.'
    if os.path.exists(sparta_json):
        processed_data = extractor.process_sparta_json(sparta_json)
        
        # Export for ArangoDB
        arangodb_output = '.'
        extractor.export_for_arangodb(processed_data, arangodb_output)
        
        print(f"\nExtraction complete!")
        print(f"Tactics: {processed_data['coverage']['total_tactics']}")
        print(f"Techniques: {processed_data['coverage']['total_techniques']}")
        print(f"Coverage by tactic:")
        for tactic, count in processed_data['coverage']['techniques_per_tactic'].items():
            print(f"  {tactic}: {count} techniques")
    else:
        logger.error(f"SPARTA JSON not found: {sparta_json}")
        

if __name__ == '__main__':
    main()
