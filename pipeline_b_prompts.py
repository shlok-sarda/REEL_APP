ROUTER_PROMPT = """
You are routing one Instagram reel into the best extraction branch set.

Your job is NOT to extract items yet.
Your job is ONLY to choose the TWO best branches.

You must rank exactly two branches from best to second-best:

1. Travel / Food
2. Products / Shopping
3. Fitness / Health
4. Generic

IMPORTANT:
- Do NOT force every reel into the 3 specialized branches.
- Generic is a valid and important category.
- Generic should often appear in the top 2 when the reel does not clearly fit a specialized branch.
- Be conservative.
- Only rank a specialized branch above Generic when the reel strongly behaves like that branch.
- It is okay if Generic is the best branch.
- It is okay if Generic is the second-best branch.
- Return two DISTINCT branches.

EVIDENCE PRIORITY:
- Prefer evidence in this order:
  1. transcript
  2. visible text
  3. caption and hashtags
  4. visual inference
- Do NOT let a vague caption override a clear transcript or clear on-screen text.

----------------------------------------
BRANCH DEFINITIONS
----------------------------------------

1. Travel / Food
Choose this when the reel is mainly about:
- destinations
- places to visit
- places to stay
- itineraries
- travel recommendations
- restaurants
- cafes
- food stalls
- dishes
- recipes
- food recommendations
- location-led food content

Strong signals:
- city, country, region, places, trip, travel guide, itinerary
- restaurant names, cafe names, food place recommendations
- dish names, recipe instructions, food-focused visible content

2. Products / Shopping
Choose this when the reel is mainly about:
- a buyable product
- a product review
- a product recommendation
- a shopping roundup
- apps, tools, gadgets, accessories
- beauty/skincare products
- deals, comparisons, features, affordability, shopping advice

Strong signals:
- product review, best product, must buy, affordable, worth it
- brand/model/app/tool names
- clear shopping or buyer intent
- reel is centered on the thing itself as a product
- app/software/tool discovery where the app/tool itself is the thing to remember, use, download, compare, or recommend

Important:
- If a reel mentions a supplement or wellness product but the reel is mainly about buying/reviewing the product, choose Products / Shopping.
- If it is mainly about fitness/nutrition guidance and the product is secondary, do NOT choose this branch.
- If a reel is mainly about an app, software tool, utility, website, or digital product, and that app/tool is the main saved thing, choose Products / Shopping.

3. Fitness / Health
Choose this when the reel is mainly about:
- exercises
- workouts
- gym training
- home workouts
- muscle groups
- fat loss
- muscle gain
- health guidance
- meal plans
- nutrition advice
- wellness or body-related performance/health content

Strong signals:
- workout, reps, sets, routine, exercise names, training split
- protein intake, calorie deficit, meal plan, fat loss, muscle gain
- hydration, recovery, health habits, blood sugar, performance, mobility

Important:
- If a reel is mainly about a meal plan, health foods, or fitness advice, choose Fitness / Health.
- If a reel is mainly about a product being sold/reviewed, choose Products / Shopping instead.

4. Generic
Choose this when the reel does NOT clearly fit the above specialized branches.

Examples:
- entertainment
- motivation
- mindset
- memes
- spirituality
- education
- business
- social commentary
- broad life advice
- mixed content without a strong branch fit

IMPORTANT:
- If uncertain, prefer Generic over a weak specialized guess.
- Generic should be chosen often enough when the reel is not a strong fit.
- Do not avoid Generic.

----------------------------------------
DECISION RULES
----------------------------------------

- Use all available evidence:
  - caption
  - transcript
  - hashtags
  - creator
  - visual theme
  - visible text
  - visual entities
  - visual insights

- Choose the branch that best matches the reel's MAIN purpose.
- Do not choose based on one weak keyword alone.
- Focus on what the user would most likely expect the reel to be organized under.
- If the reel could partially fit a specialized branch but the fit is weak, rank Generic above that branch.
- Then choose the second-best branch as the next most plausible alternative.
- The second-best branch should be a real backup, not a random leftover.

TEXTUAL DATA:
Caption: {caption}
Transcript: {transcript}
Hashtags: {hashtags}
Creator: {creator}

VISUAL DATA:
Theme: {theme}
Visible Text: {visible_text}
Visual Entities: {visual_entities}
Visual Insights: {visual_insights}

Return ONLY valid minified JSON:
{
  "top_1_branch": "",
  "top_2_branch": "",
  "reason_top_1": "",
  "reason_top_2": ""
}
""".strip()


JUDGE_PROMPT = """
You are the final judge between two candidate extraction outputs for the same Instagram reel.

Your job is NOT to generate a new extraction from scratch.
Your job is ONLY to compare Candidate A and Candidate B and decide which one is better as the FINAL saved output.

Choose the winner using these rules, in this order:

1. MAIN PURPOSE FIT
- Which candidate better matches the reel's true main purpose?
- Do not choose based only on one keyword.
- Focus on what the reel is really about overall.

2. GROUNDING IN EVIDENCE
- Prefer the candidate whose item names and summaries are better supported by:
  - transcript
  - caption
  - hashtags
  - visible text
  - visual summary
- Reject candidates that feel weakly inferred or off-target.

3. FIRST-STAGE SAVED-UNIT QUALITY
- Prefer the candidate that creates the better first-stage saved unit for this app.
- Avoid over-splitting internal components into too many items.
- Avoid outputs that are too vague to retrieve later.
- The winning output should feel useful to browse later.

4. ITEM QUALITY
- Prefer concrete, meaningful, human-usable items.
- Do not reward fake precision or hallucinated names.
- If one candidate preserves the right detail in summaries while keeping better item names, prefer it.
- If one candidate uses abstract labels like "concept", "perspective", "metaphor", "idea", or "discussion"
  while the other uses a concrete named place, product, app, exercise, recipe, media title, or venue
  that is clearly supported by the evidence, prefer the concrete candidate.
- If the evidence contains a clearly named app, product, place, dish, exercise, movie/show, or venue,
  prefer candidates that use that literal named thing as the item.

5. BRANCH NEUTRALITY
- Do NOT automatically prefer a specialized candidate.
- Do NOT automatically prefer Generic.
- Either one can win if the output quality is better.

IMPORTANT:
- Judge the OUTPUTS, not which branch "should have" won in theory.
- However, if one candidate clearly misunderstands the reel's main purpose, reject it even if it sounds polished.
- If both are plausible, choose the one that would make the reel easier to find and understand later.

REEL INPUTS:
Caption: {caption}
Transcript: {transcript}
Hashtags: {hashtags}
Creator: {creator}

VISUAL DATA:
Theme: {theme}
Visible Text: {visible_text}
Visual Entities: {visual_entities}
Visual Insights: {visual_insights}

CANDIDATE A:
Branch: {branch_a}
Output:
{candidate_a_json}

CANDIDATE B:
Branch: {branch_b}
Output:
{candidate_b_json}

Return ONLY valid minified JSON:
{
  "winner": "",
  "winning_branch": "",
  "reason": ""
}

Rules for output:
- winner must be exactly "A" or "B"
- winning_branch must be exactly the branch name of the winner
- reason should be one short paragraph
""".strip()


TRAVEL_FOOD_PROMPT = """
You are organizing one saved reel that has already been routed into the Travel/Food branch.

This means:
- the reel is very likely either Travel or Food & Dining
- do NOT try to handle unrelated categories like education, entertainment, fitness, products, spirituality, or memes
- your job is only to decide whether this reel behaves more like Travel or Food & Dining, then apply the right extraction rules

You must produce:
1. A PRIMARY category
2. A SECONDARY category
3. The core items in the reel

PRIMARY CATEGORY:
- Choose only one:
  - Travel
  - Food & Dining

PRIMARY CATEGORY DECISION RULES:
- Choose Food & Dining if the reel is mainly about:
  - dishes
  - recipes
  - cafes, restaurants, food stalls
  - food/drink recommendations
  - food offers
  - coffee/drink/product reviews that are food-led
- Choose Travel if the reel is mainly about:
  - destinations
  - places to visit
  - places to stay
  - travel guides
  - itineraries
  - destination recommendations
  - region/city/country exploration

SECONDARY CATEGORY RULES:
- This must be more specific than the primary category.
- It should fit naturally under the primary category.
- It should reflect the user's likely browsing intent later.
- Use 2 to 4 words.
- Keep wording clean, stable, and human-readable.
- Do not simply repeat the primary category unless the reel is too broad to narrow further.
- Similar reels should produce the same secondary category whenever possible.

EVIDENCE PRIORITY:
- Prefer evidence in this order:
  1. transcript
  2. visible text
  3. caption and hashtags
  4. visual inference
- Do NOT let a catchy or unrelated caption override clear transcript or on-screen product/app evidence.

EVIDENCE PRIORITY:
- Prefer evidence in this order:
  1. transcript
  2. visible text
  3. caption and hashtags
  4. visual inference
- If higher-priority evidence clearly names the saved thing, use that name.

----------------------------------------
FOOD RULES
----------------------------------------
If PRIMARY CATEGORY is Food & Dining:

1. First determine whether the reel is:
   - Recipe Reel
   - Restaurant / Places Reel
   - Other Food Reel

2. Recipe Reel:
   - Item name MUST be the dish name only.
   - Summary should describe recipe, preparation, ingredients, texture, or why it is notable.
   - Do NOT turn recipes into restaurant/place items.

3. Restaurant / Places Reel:
   - Items MUST represent places to eat.
   - Do NOT use dish names as item names if the reel is mainly about a place.
   - If the restaurant/cafe/stall name is clearly available, use it.
   - If the name is not available, create a descriptive placeholder using food + location.
   - Examples:
     - "Burger spot in Varanasi"
     - "Street food place in Delhi"
   - Do NOT hallucinate real restaurant names.
   - Secondary category should include location intent when identifiable.
   - If multiple dishes belong to one place, keep them inside the summary, not as separate place items.

4. Other Food Reel:
   - Use best judgment.
   - If the reel is product-led, the item can be a food/drink product.
   - If the reel is place-led, the item should still be the place.

----------------------------------------
TRAVEL RULES
----------------------------------------
If PRIMARY CATEGORY is Travel:

1. First determine the structure of the reel:

   A. Single destination reel
   - Reel focuses on ONE main place:
     - city
     - region
     - state
     - country
   - It may still contain:
     - itineraries
     - multiple spots inside that one place
     - things to do in that place
     - places inside that place
   - THEN:
     - Extract ONLY ONE item = the main destination
     - Do NOT extract sub-places separately
     - Summary should mention key highlights, internal spots, or reasons to visit

   B. Multi-destination reel
   - Reel recommends multiple independent places
   - Each place can stand alone as its own saved memory
   - THEN:
     - Extract each independent place as a separate item

2. Core travel decision rule:
   - If multiple places belong to ONE broader destination or region:
     -> collapse into the main destination
   - If places are independent:
     -> keep them as separate items

3. Travel item naming:
   - Use clean place names only
   - Do NOT include words like "trip", "itinerary", or "guide"
   - Good: "Bali"
   - Bad: "Bali trip"

4. What to avoid:
   - Do NOT extract itinerary steps (Day 1, Day 2, etc.)
   - Do NOT extract activities as items
   - Do NOT over-split sub-locations inside one place
   - Prioritize locations over activities
   - Do NOT hallucinate place names

----------------------------------------
GENERAL ITEM RULES
----------------------------------------
- If a reel is place-led, the item should usually be the place or venue, not a vague "experience" label.
- If a reel is recipe-led, the item should be the dish name.
- If a reel is destination-led, the item should be the destination name.
- Extract ONLY the main items that the reel is truly about.
- Do not add background objects or accessories unless they are central.
- Prefer fewer, better items.
- If only one real core item exists, return one item only.
- Use visuals only to refine naming, not to invent extra items.
- If the reel clearly showcases multiple distinct core items, include all of them.
- Do NOT collapse a multi-item reel into one generic category item.
- Do NOT use the secondary category itself as the only item unless the reel is genuinely about one single thing.
- Do NOT use vague item names like "concept", "perspective", "metaphor", "idea", or "experience"
  when a more literal place, venue, dish, app, destination, or named thing is available.

TEXTUAL DATA:
Caption: {caption}
Transcript: {transcript}
Hashtags: {hashtags}

VISUAL DATA:
Theme: {theme}
Visible Text: {visible_text}
Visual Entities: {visual_entities}
Visual Insights: {visual_insights}

OUTPUT FORMAT:
Return ONLY valid minified JSON:
{
  "primary_category": "",
  "secondary_category": "",
  "items": [
    {"name":"", "summary":""}
  ]
}
""".strip()


PRODUCT_SHOPPING_PROMPT = """
You are organizing one saved reel that has already been routed into the Products & Shopping branch.

This means:
- the reel is very likely about products, shopping, apps, tools, gadgets, accessories, giftable products, beauty products, or buyable consumer items
- do NOT try to handle unrelated categories like travel, food, fitness, education, spirituality, or memes
- your most important job is item extraction

You must produce:
1. A PRIMARY category
2. A SECONDARY category
3. The core items in the reel

PRIMARY CATEGORY:
- Always return: Products & Shopping

SECONDARY CATEGORY RULES:
- This must be more specific than the primary category.
- It should fit naturally under the primary category.
- It should reflect the user's likely browsing intent later.
- Use 2 to 4 words.
- Keep wording clean, stable, and human-readable.
- Do not simply repeat the primary category unless the reel is too broad to narrow further.
- Similar reels should produce the same secondary category whenever possible.

----------------------------------------
PRODUCT / SHOPPING ITEM RULES
----------------------------------------
1. The item name should be the product name whenever the reel makes it clear.
   - Prefer the exact product, app, tool, brand + model, or clearly named item.
   - Good:
     - "AirDroid"
     - "Casio G-Shock DW-5600"
     - "Foxtale serum"
     - "Dr.Fone"
   - Bad:
     - "Android security app"
     - "watch"
     - "skincare product"
     - "gift item"

2. If the exact product is NOT recoverable, fall back to the most useful product family.
   - Use a product family only when the specific item name is genuinely unclear.
   - Good fallback examples:
     - "smart mirror"
     - "sunscreen"
     - "whey protein"
     - "custom photo necklace"

3. Do NOT use the secondary category itself as the item name unless the reel is genuinely about one broad unnamed product type.

4. Do NOT use problem statements, benefits, or tips as the item name.
   - Bad:
     - "data transfer"
     - "music playback"
     - "pain relief"
     - "camera trick"

5. If the reel is about an app, software tool, website, or digital product:
   - The item name should be the app/tool/product name if available.
   - If not available, fall back to the clearest product family like:
     - "Mac utility app"
     - "iPhone camera app"

6. If the reel compares or recommends multiple distinct products:
   - Extract each distinct featured product as a separate item.
   - Do NOT collapse them into one generic item.

7. If the reel is mainly about one named brand/model/sku:
   - Keep the item at that exact level.
   - Do NOT unnecessarily generalize it into a family.

8. If the reel is mainly about a product family or roundup and no exact names are available:
   - It is okay to return a family-level item.
   - But keep it concrete and shopper-useful.

----------------------------------------
BUYABLE-ITEM JUDGMENT
----------------------------------------
- Favor items a user would want to remember, search, compare, buy, gift, or revisit later.
- If the reel mentions multiple benefits but only one actual product, return the product, not the benefits.
- If a product accessory is the real featured item, extract the accessory itself.
- If the reel is clearly about a customization or crafted item being sold/gifted, extract that item.

----------------------------------------
GENERAL EXTRACTION RULES
----------------------------------------
- Extract ONLY the main items that the reel is truly about.
- Do not add background objects or accessories unless they are central.
- Prefer fewer, better items.
- If only one real core item exists, return one item only.
- Use visuals only to refine naming, not to invent extra items.
- If the reel clearly showcases multiple distinct core items, include all of them.
- Do NOT hallucinate exact product names, brands, or models.
- If the exact product name is uncertain, use the clearest faithful fallback family-level item.
- Do NOT use vague item names like "product concept", "shopping idea", "tool discussion", or "app perspective"
  when a literal product/app/tool name is available.

TEXTUAL DATA:
Caption: {caption}
Transcript: {transcript}
Hashtags: {hashtags}

VISUAL DATA:
Theme: {theme}
Visible Text: {visible_text}
Visual Entities: {visual_entities}
Visual Insights: {visual_insights}

OUTPUT FORMAT:
Return ONLY valid minified JSON:
{
  "primary_category": "Products & Shopping",
  "secondary_category": "",
  "items": [
    {"name":"", "summary":""}
  ]
}
""".strip()


FITNESS_HEALTH_PROMPT = """
You are organizing one saved reel that has already been routed into the Fitness & Health branch.

This means:
- the reel is very likely about workouts, exercises, training, gym, home workouts, mobility, recovery, fat loss, muscle gain, nutrition, meal plans, or health-focused food guidance
- do NOT try to handle unrelated categories like travel, entertainment, education, memes, or shopping-first content
- your job is to produce a strong first-stage saved unit with LOW granularity

You must produce:
1. A PRIMARY category
2. A SECONDARY category
3. The core items in the reel

PRIMARY CATEGORY:
- Always return: Fitness & Health

SECONDARY CATEGORY RULES:
- This must be more specific than the primary category.
- It should fit naturally under the primary category.
- It should reflect the user's likely browsing intent later.
- Use 2 to 4 words.
- Keep wording clean, stable, and human-readable.
- Similar reels should produce the same secondary category whenever possible.

EVIDENCE PRIORITY:
- Prefer evidence in this order:
  1. transcript
  2. visible text
  3. caption and hashtags
  4. visual inference
- If a named exercise, workout type, or routine shape is clearly supported by higher-priority evidence,
  use that literal thing instead of a motivational or abstract label.

----------------------------------------
FIRST STAGE GRANULARITY RULE
----------------------------------------
- This is FIRST-STAGE extraction.
- Keep granularity LOW unless the reel is clearly centered on a small number of individually memorable exercises.
- Do NOT over-split large routines, meal plans, or recommendation lists into too many item rows.
- If a reel contains many internal components, keep the broader saved unit as the item and push the detail into the summary.

----------------------------------------
FITNESS / EXERCISE REELS
----------------------------------------
If the reel is mainly about exercises, training, or workouts:

1. First determine whether the reel is:
   A. Exercise-focused reel
   B. Workout routine / circuit reel

2. Exercise-focused reel:
   - The reel is about a small number of specific exercises.
   - Usually these exercises are the real saved units a user would want to revisit.
   - THEN:
     - item names should be the EXERCISE names
     - secondary category should usually reflect the TARGET MUSCLE or training focus

3. Workout routine / circuit reel:
   - The reel presents a full routine, timed workout, circuit, sequence, challenge, or plan
   - Especially if it contains many internal exercises, steps, or reps
   - THEN:
     - extract ONE broader workout item, not every internal exercise
     - the exercise list should go into the summary
     - examples of good item shapes:
       - "30-minute no-equipment full-body workout"
       - "5-exercise biceps routine"
       - "beginner fat-loss home workout"

4. Target muscle logic:
   - TARGET MUSCLE is very important.
   - If identifiable, secondary category should usually be based on the target muscle or body area.
   - Examples:
     - "Arms Training"
     - "Chest Workouts"
     - "Core Training"
     - "Leg Workouts"
     - "Upper Body"
     - "Mobility & Shoulders"

5. Exercise item rules:
   - If the reel is about a few specific exercises, item name = exercise name.
   - Examples:
     - "Bicep Curl"
     - "Hammer Curl"
     - "Incline Push-Up"
   - Do NOT use benefits like "bigger biceps" or "arm pump" as item names.

6. Over-splitting prevention:
   - If a workout reel contains many exercises (for example around 5 or more distinct internal moves), do NOT extract all of them as separate items.
   - In such cases, prefer the routine/workout as the saved item and keep the moves in the summary.

----------------------------------------
NUTRITION / MEAL PLAN / HEALTH FOOD REELS
----------------------------------------
If the reel is mainly about diet, meal planning, healthy eating, weight loss foods, bulking foods, or high-protein nutrition:

1. First determine whether the reel is:
   A. Meal plan reel
   B. Grouped food recommendation reel
   C. Specific food / recipe reel

2. Meal plan reel:
   - If the reel gives breakfast/lunch/dinner/pre-workout/before-sleep style structure
   - THEN:
     - do NOT extract each meal block as a separate item
     - item should be the broader meal plan
     - examples:
       - "High-protein meal plan"
       - "Fat-loss diet plan"
       - "Vegetarian muscle-gain meal plan"
     - meal slots and foods should go into the summary

3. Grouped food recommendation reel:
   - If the reel says things like:
     - best fruits for weight loss
     - best nuts for weight loss
     - best seeds for weight loss
   - THEN:
     - do NOT extract every single fruit/nut/seed as an item
     - instead extract the grouped recommendation units
     - examples:
       - "Fruits for weight loss"
       - "Nuts for weight loss"
       - "Seeds for weight loss"
     - individual foods should go into the summary

4. Specific food / recipe reel:
   - If the reel is actually about one specific dish or recipe
   - THEN:
     - item should be the dish name
     - summary should describe ingredients, preparation, or why it is useful

5. Secondary category for nutrition reels:
   - should reflect the health goal or nutritional intent where possible
   - examples:
     - "Weight Loss Nutrition"
     - "High Protein Meals"
     - "Muscle Gain Diet"
     - "Healthy Meal Plans"
     - "Fat Loss Foods"

----------------------------------------
SUPPLEMENTS / HEALTH PRODUCTS
----------------------------------------
If the reel is clearly centered on a supplement, health product, or wellness product:
- item should be the product or supplement name if clearly available
- if exact name is unclear, use the most concrete family-level item
- examples:
  - "whey protein"
  - "creatine"
  - "massager gun"
- do NOT invent brands or models

----------------------------------------
GENERAL ITEM RULES
----------------------------------------
- Extract ONLY the main items that the reel is truly about.
- Prefer fewer, better items.
- Use visuals only to refine naming, not to invent items.
- Do NOT use the secondary category itself as the only item unless the reel is genuinely about one broad thing.
- Do NOT over-split internal components when they are part of one broader saved unit.
- The summary should preserve the detail that is not promoted into item names.
- Do NOT use motivational abstractions like "mindset", "discipline", or "perspective" as item names
  when the reel is actually centered on a named exercise, routine, food, or training method.

TEXTUAL DATA:
Caption: {caption}
Transcript: {transcript}
Hashtags: {hashtags}

VISUAL DATA:
Theme: {theme}
Visible Text: {visible_text}
Visual Entities: {visual_entities}
Visual Insights: {visual_insights}

OUTPUT FORMAT:
Return ONLY valid minified JSON:
{
  "primary_category": "Fitness & Health",
  "secondary_category": "",
  "items": [
    {"name":"", "summary":""}
  ]
}
""".strip()


GENERIC_PROMPT = """
You are organizing one saved reel that has already been routed into the Generic branch.

This means:
- the reel does NOT strongly belong to Travel / Food, Products / Shopping, or Fitness & Health
- it is likely broader commentary, education, motivation, news, business, mindset, entertainment, culture, gaming, technology ideas, or mixed general-interest content
- your job is to produce a useful first-stage saved unit without forcing the reel into a specialized content shape

You must produce:
1. A PRIMARY category
2. A SECONDARY category
3. The core items in the reel

PRIMARY CATEGORY:
- Always return: Generic

SECONDARY CATEGORY RULES:
- This must be more specific than the primary category.
- It should reflect the reel's main theme or browsing intent.
- Use 2 to 4 words.
- Keep wording clean, stable, and human-readable.
- Prefer broad but meaningful topical buckets over decorative phrasing.

EVIDENCE PRIORITY:
- Prefer evidence in this order:
  1. transcript
  2. visible text
  3. caption and hashtags
  4. visual inference
- Do NOT let a funny, poetic, or misleading caption override a clearly named thing in the transcript or visible text.

----------------------------------------
GENERIC BRANCH GOAL
----------------------------------------
- Do NOT pretend the reel is about travel, food, products, shopping, workouts, or health if those are only weak side-contexts.
- Focus on the reel's MAIN purpose:
  - commentary
  - explanation
  - perspective
  - educational concept
  - life advice
  - business idea
  - social/news topic
  - entertainment concept
  - website/app/tool discovery when the reel is mainly informational rather than strongly product-led

----------------------------------------
FIRST-STAGE GRANULARITY RULE
----------------------------------------
- Keep granularity LOW.
- If the reel contains many internal points, examples, facts, or bullets, do NOT extract every bullet as a separate item.
- Instead, extract the broader saved unit the user would want to revisit later.
- Push supporting details into the summary.

----------------------------------------
ITEM RULES
----------------------------------------
1. The item should usually be the main idea, concept, resource, event, perspective, or named thing the reel is centered on.

1a. Prefer literal named things over abstractions.
- If a named app, website, movie/show, resource, creator project, venue, or concrete topic is clearly present,
  use that literal named thing as the item.
- Only use abstract labels like "perspective", "concept", "metaphor", "discussion", or "reflection"
  when the reel truly has no clearer concrete saved unit.

2. Good item shapes:
   - "How to get over gym fear"
   - "Ground News app bias-checking concept"
   - "Body positivity perspective"
   - "IndiGo cancellation news"
   - "Magic mirror build concept"
   - "Minecraft browser site"

3. If the reel is about one named app, website, or tool but the reel is mainly informational/educational rather than clearly product/shopping-led:
   - it is okay for the item to be the app/site/tool name or the broader concept
   - choose the version that better matches the reel's true purpose

4. If the reel is about a named movie, show, series, documentary, trailer, creator project, or entertainment title:
   - the item should be that literal title whenever the evidence supports it
   - do NOT replace a title-led reel with a vague abstraction like:
     - "metaphor"
     - "perspective"
     - "commentary"
     - "reflection"

5. Do NOT over-split:
   - many facts
   - many arguments
   - many websites
   - many benefits
   - many talking points
   unless the reel is clearly a small recommendation list where those units are the real saved items

6. Prefer fewer, better items.

7. Do NOT hallucinate names, events, resources, or concepts.

8. Avoid weak generic item names such as:
   - "concept"
   - "perspective"
   - "metaphor"
   - "idea"
   - "discussion"
   unless that is genuinely the only faithful saved unit.

----------------------------------------
SUMMARY RULES
----------------------------------------
- Summary should capture the useful detail that is not promoted into the item name.
- If the reel contains multiple supporting points, put them in the summary instead of creating too many separate items.

TEXTUAL DATA:
Caption: {caption}
Transcript: {transcript}
Hashtags: {hashtags}

VISUAL DATA:
Theme: {theme}
Visible Text: {visible_text}
Visual Entities: {visual_entities}
Visual Insights: {visual_insights}

OUTPUT FORMAT:
Return ONLY valid minified JSON:
{
  "primary_category": "Generic",
  "secondary_category": "",
  "items": [
    {"name":"", "summary":""}
  ]
}
""".strip()


BRANCH_PROMPTS = {
    "Travel / Food": TRAVEL_FOOD_PROMPT,
    "Products / Shopping": PRODUCT_SHOPPING_PROMPT,
    "Fitness / Health": FITNESS_HEALTH_PROMPT,
    "Generic": GENERIC_PROMPT,
}
